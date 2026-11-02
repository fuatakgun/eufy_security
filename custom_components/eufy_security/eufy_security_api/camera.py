import asyncio
import contextlib
from enum import Enum
import logging
import threading
from base64 import b64decode
from collections import deque
import datetime
import traceback

from .const import MessageField, STREAM_TIMEOUT_SECONDS, STREAM_SLEEP_SECONDS, GO2RTC_RTSP_PORT
from .const import SWITCH_STOP_TIMEOUT_SECONDS, COMMAND_TIMEOUT_SECONDS
from .event import Event
from .exceptions import CameraRTSPStreamNotEnabled, CameraRTSPStreamNotSupported
from .p2p_streamer import P2PStreamer
from .product import Device
from .util import wait_for_value

_LOGGER: logging.Logger = logging.getLogger(__package__)

# user starts on a station, one at a time: the add-on keeps one P2P stream per station
_station_start_locks = {}


class StreamStatus(Enum):
    """Stream status"""

    IDLE = "idle"
    PREPARING = "preparing"
    STREAMING = "streaming"


class StreamProvider(Enum):
    """Stream provider"""

    RTSP = "{rtsp_stream_url}"  # replace with rtsp url from device
    P2P = "rtsp://{server_address}:{server_port}/{serial_no}"  # replace with stream name


class PTZCommand(Enum):
    """Pan Tilt Zoom Camera Commands"""

    ROTATE360 = 0
    LEFT = 1
    RIGHT = 2
    UP = 3
    DOWN = 4


class Camera(Device):
    """Device as Camera"""

    def __init__(self, api, serial_no: str, properties: dict, metadata: dict, commands: [], config, is_rtsp_streaming: bool, is_p2p_streaming: bool, voices: dict) -> None:
        super().__init__(api, serial_no, properties, metadata, commands)

        self.stream_status: StreamStatus = StreamStatus.IDLE
        self.stream_provider: StreamProvider = None
        self.stream_url: str = None

        self.video_queue = deque()
        self.audio_queue = deque()
        self.config = config
        self.voices = voices
        self.image_last_updated = None

        self.stream_future = None
        self.stream_checker = None
        self.stop_requested = False
        self.late_stop = None
        self.stopped_by_switch = False

        self.p2p_streamer = P2PStreamer(self)

        if self.is_rtsp_enabled is True:
            self.set_stream_provider(StreamProvider.RTSP)
        else:
            self.set_stream_provider(StreamProvider.P2P)

        self.p2p_started_event = asyncio.Event()
        self.p2p_stopped_event = asyncio.Event()
        self.rtsp_started_event = asyncio.Event()

        self.stream_debug = None

    @property
    def is_streaming(self) -> bool:
        """Is Camera in Streaming Status"""
        return self.stream_status == StreamStatus.STREAMING

    async def _handle_livestream_started(self, event: Event):
        # automatically find this function for respective event
        _LOGGER.debug(f"_handle_livestream_started - {event}")
        self.p2p_started_event.set()
        if self.stop_requested is True:
            # a start landed after a user stop, stop it again; not awaited, the response arrives on this message loop
            self.late_stop = asyncio.create_task(self._stop_late_start())

    async def _stop_late_start(self):
        if self.stop_requested is False:
            # a user start came in before this task ran, keep its stream
            return
        _LOGGER.debug("_stop_late_start - livestream started after stop was requested")
        try:
            await self.api.stop_livestream(self.product_type, self.serial_no)
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.debug(f"_stop_late_start - stop failed {ex}")

    async def _handle_livestream_stopped(self, event: Event):
        # automatically find this function for respective event
        _LOGGER.debug(f"_handle_livestream_stopped - {event}")
        self.stream_status = StreamStatus.IDLE
        self.p2p_stopped_event.set()
        self.video_queue = deque()
        self.audio_queue = deque()

    async def _handle_rtsp_livestream_started(self, event: Event):
        # automatically find this function for respective event
        _LOGGER.debug(f"_handle_rtsp_livestream_started - {event}")
        self.rtsp_started_event.set()

    async def _handle_rtsp_livestream_stopped(self, event: Event):
        # automatically find this function for respective event
        _LOGGER.debug(f"_handle_rtsp_livestream_stopped - {event}")
        self.stream_status = StreamStatus.IDLE

    async def _handle_livestream_video_data_received(self, event: Event):
        #_LOGGER.debug(f"_handle_rtsp_livestream_stopped - {event}")
        self.video_queue.append(bytearray(event.data["buffer"]["data"]))

    async def _handle_livestream_audio_data_received(self, event: Event):
        pass
        #self.audio_queue.append(bytearray(event.data["buffer"]["data"]))

    async def _initiate_start_stream(self, stream_type) -> bool:
        self.set_stream_provider(stream_type)
        self.stream_status = StreamStatus.PREPARING
        self.stream_debug = "info - send command to add-on"
        _LOGGER.debug(f"_initiate_start_stream - {self.stream_debug} - {stream_type}")
        event = None
        if stream_type == StreamProvider.P2P:
            event = self.p2p_started_event
            event.clear()
            # bounded: a result future is never failed when the socket closes, and a user start holds the station lock
            try:
                if await asyncio.wait_for(self.api.start_livestream(self.product_type, self.serial_no), COMMAND_TIMEOUT_SECONDS) is False:
                    return False
            except asyncio.TimeoutError:
                # a failed start: the HA entity then stops, and a late "livestream started" is stopped
                self.stream_debug = "error - start command result timed out"
                _LOGGER.debug(f"_initiate_start_stream - {self.stream_debug}")
                return False
        else:
            event = self.rtsp_started_event
            event.clear()
            if await self.api.start_rtsp_livestream(self.product_type, self.serial_no) is False:
                return False

        try:
            await asyncio.wait_for(event.wait(), STREAM_TIMEOUT_SECONDS)
            self.stream_debug = "info - command was done"
            _LOGGER.debug(f"_initiate_start_stream - {self.stream_debug}")
            return True
        except asyncio.TimeoutError:
            self.stream_debug = f"error - command was failed - {event}"
            _LOGGER.debug(f"_initiate_start_stream - {self.stream_debug}")
            return False

    async def _check_live_stream(self):
        while self.p2p_streamer.retry is None:
            await asyncio.sleep(0.5)

        _LOGGER.debug(f"async_restart_livestream - start - {self.p2p_streamer.retry}")
        if self.stream_status != StreamStatus.IDLE:
            await self.stop_livestream(is_internal=True)

        # a user stop wins over a retry raised by the go2rtc push
        if self.p2p_streamer.retry is True and self.stop_requested is False:
            _LOGGER.debug(f"async_restart_livestream - start live stream start - {self.p2p_streamer.retry}")
            await self.start_livestream(is_internal=True)
            _LOGGER.debug(f"async_restart_livestream - start live stream end - {self.p2p_streamer.retry}")

    async def start_livestream(self, is_internal=False) -> bool:
        """Process start p2p livestream call"""
        station = self.properties.get("stationSerialNumber")
        lock = asyncio.Lock() if station is None else _station_start_locks.setdefault(station, asyncio.Lock())
        if is_internal is True:
            async with lock:
                if await self._other_station_streaming() is True:
                    # an auto-restart must not take over another camera's stream
                    _LOGGER.debug(f"start_livestream - {self.serial_no} not restarted, another camera on the station streams")
                    return False
                return await self._start_p2p_livestream()
        self.stop_requested = False
        async with lock:
            if self.stopped_by_switch is True:
                # another camera's switch stopped this one while this start waited; the newer start wins
                self.stop_requested = False
            if self.stream_status == StreamStatus.STREAMING and self.stream_provider == StreamProvider.P2P:
                # an earlier start of this camera already streams it; a second start command would fail
                return True
            await self._stop_other_station_streams()
            if self.stop_requested is True:
                # stop was called while waiting for the other camera
                return False
            return await self._start_p2p_livestream()

    async def _start_p2p_livestream(self) -> bool:
        if await self._initiate_start_stream(StreamProvider.P2P) is False:
            return False
        if self.stop_requested is True:
            # stop was called while this start was in progress; _handle_livestream_started stops the device stream
            _LOGGER.debug("start_livestream - stop requested during start")
            return False
        self.stream_future = asyncio.create_task(self.p2p_streamer.start())
        self.stream_checker = asyncio.create_task(self._check_live_stream())
        self.stream_status = StreamStatus.STREAMING
        return True

    async def _is_streaming(self) -> bool:
        """Ask the add-on; None when the answer is unknown"""
        try:
            return await asyncio.wait_for(self.api._get_is_p2p_streaming(self.product_type, self.serial_no), COMMAND_TIMEOUT_SECONDS)
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.debug(f"_is_streaming - {self.serial_no} is_livestreaming failed {ex}")
            return None

    async def _other_station_streaming(self) -> bool:
        """Another camera on this station streams, or the add-on cannot tell"""
        station = self.properties.get("stationSerialNumber")
        if station is None:
            return False
        for device in list(self.api.devices.values()):
            if device is self or isinstance(device, Camera) is False:
                continue
            if device.properties.get("stationSerialNumber") == station and await device._is_streaming() is not False:
                return True
        return False

    async def _stop_other_station_streams(self):
        """Stop another camera's P2P stream on this station before a user start: the add-on keeps one P2P stream
        per station, and a stream that took over another one has ignored its later stop"""
        station = self.properties.get("stationSerialNumber")
        if station is None:
            return
        for device in list(self.api.devices.values()):
            if device is self or isinstance(device, Camera) is False:
                continue
            if device.properties.get("stationSerialNumber") != station:
                continue
            # unknown counts as streaming: a needless stop only fails with livestream_not_running
            streaming = await device._is_streaming()
            if self.stop_requested is True:
                return
            if streaming is False:
                continue
            _LOGGER.debug(f"start_livestream - {self.serial_no} stops {device.serial_no} first")
            device.p2p_stopped_event.clear()
            try:
                # one bound for the stop command and its event
                await asyncio.wait_for(device._stop_and_wait(), SWITCH_STOP_TIMEOUT_SECONDS)
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.debug(f"start_livestream - stop of {device.serial_no} not confirmed {ex}")

    async def _stop_and_wait(self):
        await self.stop_livestream(by_switch=True)
        await self.p2p_stopped_event.wait()

    async def stop_livestream(self, is_internal=False, by_switch=False):
        """Process stop p2p livestream call"""
        if is_internal is True:
            # called from another function, so respect retry value
            pass
        else:
            self.p2p_streamer.retry = False
            # a switch stop never replaces a user stop that is still pending
            self.stopped_by_switch = by_switch is True and not (self.stop_requested is True and self.stopped_by_switch is False)
            self.stop_requested = True
            # an older checker must not stop or restart anything after a user stop
            if self.stream_checker is not None:
                self.stream_checker.cancel()
        await self.api.stop_livestream(self.product_type, self.serial_no)

    async def start_rtsp_livestream(self) -> bool:
        """Process start rtsp livestream call"""
        if await self._initiate_start_stream(StreamProvider.RTSP) is False:
            return False

        self.stream_status = StreamStatus.STREAMING
        return True


    async def stop_rtsp_livestream(self):
        """Process stop rtsp livestream call"""
        await self.api.stop_rtsp_livestream(self.product_type, self.serial_no)

    async def ptz(self, direction: str) -> None:
        """Parameterized PTZ function"""
        await self.api.pan_and_tilt(self.product_type, self.serial_no, PTZCommand[direction].value)

    async def ptz_up(self) -> None:
        """Look up"""
        await self.api.pan_and_tilt(self.product_type, self.serial_no, PTZCommand.UP.value)

    async def ptz_down(self) -> None:
        """Look down"""
        await self.api.pan_and_tilt(self.product_type, self.serial_no, PTZCommand.DOWN.value)

    async def ptz_left(self) -> None:
        """Look left"""
        await self.api.pan_and_tilt(self.product_type, self.serial_no, PTZCommand.LEFT.value)

    async def ptz_right(self) -> None:
        """Look right"""
        await self.api.pan_and_tilt(self.product_type, self.serial_no, PTZCommand.RIGHT.value)

    async def ptz_360(self) -> None:
        """Look around 360 degrees"""
        await self.api.pan_and_tilt(self.product_type, self.serial_no, PTZCommand.ROTATE360.value)

    async def preset_position(self, position: int) -> None:
        """Set preset position"""
        await self.api.preset_position(self.product_type, self.serial_no, position)

    async def save_preset_position(self, position: int) -> None:
        """Save new preset position"""
        await self.api.save_preset_position(self.product_type, self.serial_no, position)

    async def delete_preset_position(self, position: int) -> None:
        """Delete existing preset position"""
        await self.api.delete_preset_position(self.product_type, self.serial_no, position)

    async def calibrate(self) -> None:
        """Calibrate camera"""
        await self.api.calibrate(self.product_type, self.serial_no)

    async def quick_response(self, voice_id: int) -> None:
        """Quick response message to camera"""
        await self.api.quick_response(self.product_type, self.serial_no, voice_id)

    @property
    def is_rtsp_supported(self) -> bool:
        """Returns True if camera supports RTSP stream"""
        return self.has(MessageField.RTSP_STREAM.value)

    @property
    def is_rtsp_enabled(self) -> bool:
        """Returns True if RTSP stream is configured and enabled for camera"""
        return False if self.is_rtsp_supported is False else self.properties.get(MessageField.RTSP_STREAM.value)

    @property
    def rtsp_stream_url(self) -> str:
        """Returns RTSP stream URL from physical device"""
        return self.properties.get(MessageField.RTSP_STREAM_URL.value)

    @property
    def picture_base64(self) -> str:
        """Returns picture bytes in base64 format"""
        return self.properties.get(MessageField.PICTURE.value)

    @property
    def picture_bytes(self):
        """Returns picture bytes in base64 format"""
        return bytearray(self.picture_base64["data"]["data"])

    def set_stream_provider(self, stream_provider: StreamProvider) -> None:
        """Set stream provider for camera instance"""
        self.stream_provider = stream_provider
        url = self.stream_provider.value

        if self.stream_provider == StreamProvider.RTSP:
            if self.is_rtsp_enabled is False:
                if self.is_rtsp_supported is False:
                    raise CameraRTSPStreamNotSupported(self.name)
                raise CameraRTSPStreamNotEnabled(self.name)

            self.stream_url = url.replace("{rtsp_stream_url}", self.rtsp_stream_url)

        elif self.stream_provider == StreamProvider.P2P:
            url = url.replace("{serial_no}", str(self.serial_no))
            url = url.replace("{server_address}", str(self.config.rtsp_server_address))
            url = url.replace("{server_port}", str(GO2RTC_RTSP_PORT))
            self.stream_url = url
        _LOGGER.debug(f"url - {self.stream_provider} - {self.stream_url}")

    async def _handle_property_changed(self, event: Event):
        await super()._handle_property_changed(event)
        _LOGGER.debug(f"camera _handle_property_changed - {event.data[MessageField.NAME.value] }")

        if event.data[MessageField.NAME.value] == MessageField.PICTURE.value:
            self.image_last_updated = datetime.datetime.now(datetime.timezone.utc)
