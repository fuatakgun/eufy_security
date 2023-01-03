import asyncio
import contextlib
from enum import Enum
import logging
from queue import Queue
import threading

from aiortsp.rtsp.reader import RTSPReader

from .const import MessageField
from .event import Event
from .exceptions import CameraRTSPStreamNotEnabled, CameraRTSPStreamNotSupported
from .p2p_stream_handler import P2PStreamHandler
from .product import Device
from .util import wait_for_value

_LOGGER: logging.Logger = logging.getLogger(__package__)

STREAM_TIMEOUT_SECONDS = 15
STREAM_SLEEP_SECONDS = 0.5


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

    def __init__(
        self,
        api,
        serial_no: str,
        properties: dict,
        metadata: dict,
        commands: [],
        config,
        is_rtsp_streaming: bool,
        is_p2p_streaming: bool,
        voices: dict,
    ) -> None:
        super().__init__(api, serial_no, properties, metadata, commands)

        self.stream_status: StreamStatus = StreamStatus.IDLE
        self.stream_provider: StreamProvider = None
        self.stream_url: str = None
        self.codec: str = None
        self.video_queue: Queue = Queue()
        self.config = config
        self.voices = voices
        self.ffmpeg = None

        self.p2p_stream_handler = P2PStreamHandler(self)
        self.p2p_stream_thread = None

        if self.is_rtsp_enabled is True:
            self.set_stream_prodiver(StreamProvider.RTSP)
        else:
            self.set_stream_prodiver(StreamProvider.P2P)

        self.p2p_started_event = asyncio.Event()
        self.rtsp_started_event = asyncio.Event()

    @property
    def is_streaming(self) -> bool:
        """Is Camera in Streaming Status"""
        return self.stream_status == StreamStatus.STREAMING

    def set_ffmpeg(self, ffmpeg):
        """set ffmpeg binary"""
        self.ffmpeg = ffmpeg
        self.p2p_stream_handler.set_ffmpeg(ffmpeg)

    async def _handle_livestream_started(self, event: Event):
        # automatically find this function for respective event
        _LOGGER.debug(f"_handle_livestream_started - {event}")

    async def _handle_livestream_stopped(self, event: Event):
        # automatically find this function for respective event
        _LOGGER.debug(f"_handle_livestream_stopped - {event}")
        self.stream_status = StreamStatus.IDLE
        self.video_queue.queue.clear()

    async def _handle_rtsp_livestream_started(self, event: Event):
        # automatically find this function for respective event
        _LOGGER.debug(f"_handle_rtsp_livestream_started - {event}")
        self.rtsp_started_event.set()

    async def _handle_rtsp_livestream_stopped(self, event: Event):
        # automatically find this function for respective event
        _LOGGER.debug(f"_handle_rtsp_livestream_stopped - {event}")
        self.stream_status = StreamStatus.IDLE

    async def _handle_livestream_video_data_received(self, event: Event):
        # automatically find this function for respective event
        if self.codec is None:
            self.codec = event.data["metadata"]["videoCodec"].lower()
            await self._start_ffmpeg()

        self.video_queue.put(bytearray(event.data["buffer"]["data"]))

    async def _start_ffmpeg(self):
        await self.p2p_stream_handler.start_ffmpeg(self.config.ffmpeg_analyze_duration)

    async def _is_stream_url_ready(self) -> bool:
        _LOGGER.debug("_is_stream_url_ready - 1")
        with contextlib.suppress(Exception):
            while True:
                async with RTSPReader(self.stream_url.replace("rtsp://", "rtspt://")) as reader:
                    _LOGGER.debug("_is_stream_url_ready - 2 - reader opened")
                    async for pkt in reader.iter_packets():
                        _LOGGER.debug(f"_is_stream_url_ready - 3 - received {len(pkt)}")
                        return True
                    _LOGGER.debug("_is_stream_url_ready - 4 - reader closed")
                await asyncio.sleep(STREAM_SLEEP_SECONDS)
        return False

    async def start_livestream(self) -> bool:
        """Process start p2p livestream call"""
        self.set_stream_prodiver(StreamProvider.P2P)
        self.stream_status = StreamStatus.PREPARING
        await self.api.start_livestream(self.product_type, self.serial_no)
        self.p2p_stream_thread = threading.Thread(target=self.p2p_stream_handler.setup, daemon=True)
        self.p2p_stream_thread.start()
        await wait_for_value(self.p2p_stream_handler.__dict__, "port", None)

        if self.codec is not None:
            await self._start_ffmpeg()

        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self.p2p_started_event.wait(), STREAM_TIMEOUT_SECONDS)

        if self.p2p_started_event.is_set() is False:
            return False

        try:
            await asyncio.wait_for(self._is_stream_url_ready(), STREAM_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            return False
        self.stream_status = StreamStatus.STREAMING
        return True

    async def stop_livestream(self):
        """Process stop p2p livestream call"""
        await self.api.stop_livestream(self.product_type, self.serial_no)
        if self.p2p_stream_thread.is_alive() is True:
            await self.p2p_stream_handler.stop()

    async def start_rtsp_livestream(self):
        """Process start rtsp livestream call"""
        self.set_stream_prodiver(StreamProvider.RTSP)
        self.stream_status = StreamStatus.PREPARING
        await self.api.start_rtsp_livestream(self.product_type, self.serial_no)
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self.rtsp_started_event.wait(), 5)

        if self.rtsp_started_event.is_set() is False:
            return False

        try:
            await asyncio.wait_for(self._is_stream_url_ready(), 5)
        except asyncio.TimeoutError:
            return False
        self.stream_status = StreamStatus.STREAMING
        return True

    async def stop_rtsp_livestream(self):
        """Process stop rtsp livestream call"""
        await self.api.stop_rtsp_livestream(self.product_type, self.serial_no)

    async def ptz(self, direction: str) -> None:
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

    def set_stream_prodiver(self, stream_provider: StreamProvider) -> None:
        """Set stream provider for camera instance"""
        self.stream_provider = stream_provider

        if self.stream_provider == StreamProvider.RTSP:
            url = self.stream_provider.value
            if self.is_rtsp_enabled is True:
                self.stream_url = url.replace("{rtsp_stream_url}", self.rtsp_stream_url)
            else:
                if self.is_rtsp_supported is False:
                    raise CameraRTSPStreamNotSupported(self.name)
                raise CameraRTSPStreamNotEnabled(self.name)
        elif self.stream_provider == StreamProvider.P2P:
            url = self.stream_provider.value
            _LOGGER.debug(f"{self.p2p_stream_handler.port}")
            url = url.replace("{serial_no}", str(self.serial_no))
            url = url.replace("{server_address}", str(self.config.rtsp_server_address))
            url = url.replace("{server_port}", str(self.config.rtsp_server_port))
            self.stream_url = url
        _LOGGER.debug(f"url - {self.stream_provider} - {self.stream_url}")
