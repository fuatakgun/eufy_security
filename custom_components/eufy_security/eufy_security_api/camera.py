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
from .event import Event
from .exceptions import CameraRTSPStreamNotEnabled, CameraRTSPStreamNotSupported
from .p2p_streamer import P2PStreamer
from .product import Device
from .util import wait_for_value

_LOGGER: logging.Logger = logging.getLogger(__package__)


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

        self.p2p_streamer = P2PStreamer(self)

        if self.is_rtsp_enabled is True:
            self.set_stream_provider(StreamProvider.RTSP)
        else:
            self.set_stream_provider(StreamProvider.P2P)

        self.p2p_started_event = asyncio.Event()
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

    async def _handle_livestream_stopped(self, event: Event):
        # automatically find this function for respective event
        _LOGGER.debug(f"_handle_livestream_stopped - {event}")
        self.stream_status = StreamStatus.IDLE
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
            if await self.api.start_livestream(self.product_type, self.serial_no) is False:
                return False
        else:
            event = self.rtsp_started_event
            event.clear()
            if await self.api.start_rtsp_livestream(self.product_type, self.serial_no) is False:
                return False

        try:
            await asyncio.wait_for(event.wait(), 5)
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

        if self.p2p_streamer.retry is True:
            _LOGGER.debug(f"async_restart_livestream - start live stream start - {self.p2p_streamer.retry}")
            await self.start_livestream()
            _LOGGER.debug(f"async_restart_livestream - start live stream end - {self.p2p_streamer.retry}")

    async def start_livestream(self) -> bool:
        """Process start p2p livestream call"""
        if await self._initiate_start_stream(StreamProvider.P2P) is False:
            return False
        self.stream_future = asyncio.create_task(self.p2p_streamer.start())
        self.stream_checker = asyncio.create_task(self._check_live_stream())
        self.stream_status = StreamStatus.STREAMING
        return True

    async def stop_livestream(self, is_internal=False):
        """Process stop p2p livestream call"""
        if is_internal is True:
            # called from another function, so respect retry value
            pass
        else:
            self.p2p_streamer.retry = False
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
