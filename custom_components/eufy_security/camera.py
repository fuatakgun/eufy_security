import logging

import asyncio
import async_timeout
import datetime
import requests
import traceback
from queue import Queue
import threading

from haffmpeg.camera import CameraMjpeg
from haffmpeg.tools import IMAGE_JPEG, ImageFrame
from homeassistant.components.camera import Camera
from homeassistant.components.camera import SUPPORT_ON_OFF, SUPPORT_STREAM
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.stream import Stream, create_stream
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers import config_validation as cv, entity_platform, service

from .const import DOMAIN, NAME, START_LIVESTREAM_AT_INITIALIZE
from .const import wait_for_value
from .entity import EufySecurityEntity
from .coordinator import EufySecurityDataUpdateCoordinator
from time import sleep

STATE_RECORDING = "Recording"
STATE_STREAMING = "Streaming"
STATE_LIVE_STREAMING = "livestream started"
STREAMING_SOURCE_RTSP = "rtsp"
STREAMING_SOURCE_P2P = "p2p"
STATE_MOTION_DETECTED = "Motion Detected"
STATE_PERSON_DETECTED = "Person Detected"
STATE_IDLE = "Idle"
FFMPEG_COMMAND = [
    "-protocol_whitelist",
    "pipe,file,tcp",
    "-f",
    "{video_codec}",
    "-i",
    "-",
    "-vcodec",
    "copy",
    "-protocol_whitelist",
    "pipe,file,tcp",
    "-y",
]
FFMPEG_OPTIONS = (
    " -hls_init_time 0"
    " -hls_time 10"
    " -hls_segment_type mpegts"
    " -hls_playlist_type event "
    " -hls_list_size 3"
    " -hls_delete_threshold 3"
    " -hls_flags delete_segments"
    " -preset veryfast"
    " -segment_wrap 3"
    " -absf aac_adtstoasc"
    " -sc_threshold 0"
    " -fflags genpts+nobuffer+flush_packets"
    " -loglevel debug"
    " -report"
)


_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass, entry, async_add_devices):
    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN]

    # if device type is CAMERA or DOORBELL, create corresponding camera entities and add
    entities = []
    for entity in coordinator.state["devices"]:
        if entity["category"] in ["CAMERA", "DOORBELL"]:
            camera: EufySecurityCamera = EufySecurityCamera(
                hass, coordinator, entry, entity
            )
            entities.append(camera)

    _LOGGER.debug(f"{DOMAIN} - camera setup entries - {entities}")
    async_add_devices(entities, True)

    # register entity level services
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "start_livestream", {}, "async_start_livestream"
    )
    platform.async_register_entity_service(
        "stop_livestream", {}, "async_stop_livestream"
    )
    platform.async_register_entity_service("start_rtsp", {}, "async_start_rtsp")
    platform.async_register_entity_service("stop_rtsp", {}, "async_stop_rtsp")


class EufySecurityCamera(EufySecurityEntity, Camera):
    def __init__(
        self,
        hass,
        coordinator: EufySecurityDataUpdateCoordinator,
        entry: ConfigEntry,
        entity: dict,
    ):
        EufySecurityEntity.__init__(self, coordinator, entry, entity)
        Camera.__init__(self)
        self.hass = hass

        # initialize values
        self.serial_number = self.entity["serialNumber"]
        self.coordinator.cache[self.serial_number] = {}
        self.cached_entity = self.coordinator.cache[self.serial_number]
        self.properties = self.coordinator.properties[self.serial_number]

        # camera image
        self.camera_picture_bytes = None
        self.camera_picture_url = None

        # ffmpeg, video generation and image capturing
        self.ffmpeg_binary = self.hass.data[DATA_FFMPEG].binary
        self.ffmpeg = CameraMjpeg(self.ffmpeg_binary)
        self.image_frame = ImageFrame(self.ffmpeg_binary)
        self.ffmpeg_output = f"{DOMAIN}-{self.serial_number}.m3u8"
        self.ffmpeg_video_thread = None
        self.ffmpeg_image_thread = None

        # for p2p streaming
        self.start_stream_function = self.async_start_livestream
        self.stop_stream_function = self.async_stop_livestream
        self.cached_entity["liveStreamingStatus"] = None
        self.cached_entity["queue"] = Queue()
        self.cached_entity["video_codec"] = None

        # when HA started, p2p streaming was active, we need to catch up
        if self.entity.get(START_LIVESTREAM_AT_INITIALIZE, False) == True:
            async_call_later(self.hass, 0, self.async_start_livestream)

        # for rtsp streaming
        self.cached_entity["rtspUrl"] = None
        if not self.entity.get("rtspStream", None) is None:
            self.start_stream_function = self.async_start_rtsp
            self.stop_stream_function = self.async_stop_rtsp

        # when HA started, rtsp streaming was active, we need to catch up
        if self.entity.get("rtspStream", False) == True:
            if self.cached_entity["rtspUrl"] is None:
                async_call_later(self.hass, 0, self.async_start_rtsp)

        self.streaming_source = None
        self.is_streaming = False

    def on_close(self, future="") -> None:
        try:
            self.ffmpeg.process.communicate()
            self.ffmpeg.kill()
        except:
            pass

    @property
    def state(self) -> str:
        self.set_is_streaming()
        if self.is_streaming:
            if not self.streaming_source is None:
                return f"{STATE_STREAMING} - {self.streaming_source}"
            return STATE_STREAMING
        elif self.entity.get("motionDetected", False):
            return STATE_MOTION_DETECTED
        elif self.entity.get("personDetected", False):
            return STATE_PERSON_DETECTED
        else:
            if not self.entity.get("battery", None) is None:
                return f"{STATE_IDLE} - {self.entity['battery']} %"
            return STATE_IDLE

    def set_is_streaming(self):
        # based on streaming options, set `is_streaming` value
        prev_is_streaming = self.is_streaming
        if (
            self.entity.get("rtspStream", False) == True
            or self.cached_entity["liveStreamingStatus"] == STATE_LIVE_STREAMING
        ):
            if self.entity.get("rtspStream", False) == True:
                if not self.cached_entity["rtspUrl"] is None:
                    self.streaming_source = STREAMING_SOURCE_RTSP
                    self.is_streaming = True
            if self.cached_entity["liveStreamingStatus"] == STATE_LIVE_STREAMING:
                self.streaming_source = STREAMING_SOURCE_P2P
                self.is_streaming = True
        else:
            self.streaming_source = None
            self.is_streaming = False

        if prev_is_streaming != self.is_streaming:
            _LOGGER.debug(
                f"{DOMAIN} {self.name} - state change - {prev_is_streaming} {self.is_streaming}"
            )

        if prev_is_streaming == False and self.is_streaming == True:
            # streaming has started, create stream for web view
            async_call_later(self.hass, 1, self.create_stream)
        elif prev_is_streaming == True and self.is_streaming == False:
            # streaming has finished, destroy stream
            self.stream.stop()
            self.stream = None

    async def initiate_turn_on(self):
        await self.hass.async_add_executor_job(self.turn_on)
        return await wait_for_value(self.__dict__, "is_streaming", False, interval=0.5)

    async def stream_source(self):
        # prepare `stream` object for web view
        _LOGGER.debug(f"{DOMAIN} {self.name} - stream_source - start")

        # if user has clicked on image view and camera was not streaming, turn_on camera
        if self.is_streaming == False:
            await self.initiate_turn_on()

        # turn_on does not guarantee that stream will start successfully, check the result
        _LOGGER.debug(
            f"{DOMAIN} {self.name} - stream_source - is_streaming - {self.is_streaming}"
        )

        if self.streaming_source == STREAMING_SOURCE_P2P:
            # setup video encoding thread for p2p streaming
            self.ffmpeg_video_thread = FFMpegVideoHandlerThread(self)
            async_call_later(self.hass, 1, self.ffmpeg_video_thread.start)
            await wait_for_value(self.ffmpeg_video_thread.__dict__, "processing", False)
            stream_source = self.ffmpeg_output
            _LOGGER.debug(f"{DOMAIN} {self.name} - create_stream p2p - {stream_source}")

        if self.streaming_source == STREAMING_SOURCE_RTSP:
            stream_source = self.cached_entity["rtspUrl"]
            _LOGGER.debug(
                f"{DOMAIN} {self.name} - create_stream rtsp - {stream_source}"
            )

        # setup live image capturing thread for rtsp/p2p streaming
        self.ffmpeg_image_thread = FFMpegImageHandlerThread(self)
        async_call_later(self.hass, 1, self.ffmpeg_image_thread.start)

        return stream_source

    async def create_stream(self, executed_at=None) -> Stream:
        self.stream = await Camera.create_stream(self)
        return self.stream

    def camera_image(self) -> bytes:
        # if streaming is active, do not overwrite live image
        if self.is_streaming == False:
            current_picture_url = self.entity.get("pictureUrl", "")
            if self.camera_picture_url != current_picture_url:
                response = requests.get(current_picture_url)
                _LOGGER.debug(
                    f"{DOMAIN} {self.name} - camera_image -{current_picture_url} {response.status_code} - {len(response.content)}"
                )
                if response.status_code == 200:
                    self.camera_picture_url = current_picture_url
                    self.camera_picture_bytes = response.content

        return self.camera_picture_bytes

    def turn_on(self) -> None:
        asyncio.run_coroutine_threadsafe(
            self.start_stream_function(),
            self.hass.loop,
        ).result()

    def turn_off(self) -> None:
        asyncio.run_coroutine_threadsafe(
            self.stop_stream_function(),
            self.hass.loop,
        ).result()

    async def async_start_livestream(self, executed_at=None) -> None:
        await self.coordinator.async_set_livestream(self.serial_number, "start")

    async def async_stop_livestream(self) -> None:
        await self.coordinator.async_set_livestream(self.serial_number, "stop")

    async def async_start_rtsp(self, executed_at=None) -> None:
        await self.coordinator.async_set_rtsp(self.serial_number, True)

    async def async_stop_rtsp(self) -> None:
        await self.coordinator.async_set_rtsp(self.serial_number, False)

    @property
    def id(self):
        return f"{DOMAIN}_{self.serial_number}_camera"

    @property
    def unique_id(self):
        return self.id

    @property
    def name(self):
        return self.entity.get("name", "Missing Name")

    @property
    def brand(self):
        return f"{NAME}"

    @property
    def model(self):
        return self.entity.get("model", "Missing Model")

    @property
    def is_on(self):
        return self.entity.get("enabled", True)

    @property
    def motion_detection_enabled(self):
        return self.entity.get("motionDetection", False)

    @property
    def state_attributes(self):
        attrs = {}
        attrs["data"] = self.entity
        attrs["debug"] = {}
        attrs["debug"]["is_streaming"] = self.is_streaming
        attrs["debug"]["streaming_source"] = self.streaming_source
        attrs["debug"]["p2p_streaming_response"] = self.cached_entity[
            "liveStreamingStatus"
        ]
        attrs["debug"]["queue_size"] = self.cached_entity["queue"].qsize()
        attrs["debug"]["rtsp_url"] = self.cached_entity["rtspUrl"]
        attrs["debug"]["properties"] = self.properties

        if self.model:
            attrs["model_name"] = self.model

        if self.brand:
            attrs["brand"] = self.brand

        if self.motion_detection_enabled:
            attrs["motion_detection"] = self.motion_detection_enabled

        return attrs

    @property
    def supported_features(self) -> int:
        return SUPPORT_ON_OFF | SUPPORT_STREAM


class FFMpegVideoHandlerThread(threading.Thread):
    def __init__(self, camera: EufySecurityCamera):
        super().__init__(daemon=True)
        self.camera = camera
        self.processing = False

    def get_video_codec(self):
        video_codec = self.camera.cached_entity["video_codec"]
        if video_codec == "h265":
            video_codec = "hevc"
        if video_codec == "unknown":
            video_codec = "h264"
        return video_codec

    def open_ffmpeg(self):
        ffmpeg_command_instance = FFMPEG_COMMAND.copy()
        input_file_index = ffmpeg_command_instance.index("-i")
        ffmpeg_command_instance[input_file_index - 1] = self.get_video_codec()

        if self.camera.ffmpeg.is_running == False:
            _LOGGER.debug(f"{DOMAIN} {self.camera.name} - starting ffmpeg")
            asyncio.run_coroutine_threadsafe(
                self.camera.ffmpeg.open(
                    cmd=ffmpeg_command_instance,
                    input_source=None,
                    extra_cmd=FFMPEG_OPTIONS,
                    output=self.camera.ffmpeg_output,
                    stderr_pipe=False,
                    stdout_pipe=False,
                ),
                self.camera.hass.loop,
            ).result()

        _LOGGER.debug(f"{DOMAIN} {self.camera.name} video_thread ffmpeg is open")

    def run(self):
        _LOGGER.debug(f"{DOMAIN} {self.camera.name} video_thread start")

        if (
            asyncio.run_coroutine_threadsafe(
                wait_for_value(self.camera.cached_entity, "video_codec", None),
                self.camera.hass.loop,
            ).result()
            == False
        ):
            return

        self.open_ffmpeg()
        self.processing = True
        queue = self.camera.cached_entity["queue"]
        _LOGGER.debug(f"{DOMAIN} {self.camera.name} - video_thread")
        while True:
            if self.camera.is_streaming == False:
                return

            _LOGGER.debug(
                f"{DOMAIN} {self.camera.name} - video_thread queue size - {queue.qsize()}"
            )
            while not queue.empty():
                try:
                    frame_bytes = bytearray(queue.get().get("data", None))
                    if not frame_bytes is None:
                        self.camera.ffmpeg.process.stdin.write(frame_bytes)
                except Exception as ex:  # pylint: disable=broad-except
                    _LOGGER.error(
                        f"{DOMAIN} {self.camera.name} video_thread exception: {ex}- traceback: {traceback.format_exc()}"
                    )
                    _, ffmpeg_error = self.camera.ffmpeg.process.communicate()
                    if ffmpeg_error is not None:
                        ffmpeg_error = ffmpeg_error.decode()
                        _LOGGER.debug(
                            f"{DOMAIN} {self.camera.name} - video ffmpeg error - {ffmpeg_error}"
                        )

            _LOGGER.debug(f"{DOMAIN} {self.camera.name} - video_thread - sleeping")
            sleep(1)

    def start(self, executed_at=None):
        self.run()

    def stop(self):
        _LOGGER.info(f"{DOMAIN} {self.camera.name} - video_thread - stopping")
        self.camera.cached_entity["queue"].queue.clear()
        self.camera.ffmpeg.process.communicate()
        self.camera.ffmpeg.kill()
        self.join()


class FFMpegImageHandlerThread(threading.Thread):
    def __init__(self, camera: EufySecurityCamera):
        super().__init__(daemon=True)
        self.camera = camera
        self.processing = False

    def run(self):
        self.processing = True
        _LOGGER.debug(
            f"{DOMAIN} {self.camera.name} - image_thread start - {self.camera.stream} {self.camera.is_streaming}"
        )
        while True:
            if self.camera.is_streaming == False:
                return

            image_frame_bytes = asyncio.run_coroutine_threadsafe(
                self.camera.image_frame.get_image(self.camera.stream.source),
                self.camera.hass.loop,
            ).result()

            if image_frame_bytes is not None:
                _LOGGER.debug(
                    f"{DOMAIN} {self.camera.name} - image_thread len - {len(image_frame_bytes)}"
                )
                if len(image_frame_bytes) > 0:
                    self.camera.camera_picture_bytes = image_frame_bytes
                    self.camera.schedule_update_ha_state(False)

            sleep(1)

    def start(self, executed_at=None):
        self.run()

    def stop(self):
        _LOGGER.info(f"{DOMAIN} {self.camera.name} - image_thread - stopping")
        self.join()
