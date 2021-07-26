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

from .const import DOMAIN, NAME
from .entity import EufySecurityEntity
from .coordinator import EufySecurityDataUpdateCoordinator
from .generated import DeviceType
from time import sleep

STATE_RECORDING = "recording"
STATE_STREAMING = "streaming"
STATE_LIVE_STREAMING = "livestream started"
STREAMING_SOURCE_RTSP = "rtsp"
STREAMING_SOURCE_P2P = "p2p"
STATE_MOTION_DETECTED = "Motion Detected"
STATE_PERSON_DETECTED = "Person Detected"
STATE_IDLE = "idle"
FFMPEG_COMMAND = [
    "-protocol_whitelist",
    "pipe,file,tcp",
    "-f",
    "{video_codec}",
    "-i",
    "-",
    "-vcodec",
    "copy",
    "-acodec",
    "copy",
    "-protocol_whitelist",
    "pipe,file,tcp",
    "-y",
]
FFMPEG_OPTIONS = (
    " -hls_init_time 0"
    " -hls_time 3"
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

    entities = []
    for entity in coordinator.state["devices"]:
        if not entity.get("pictureUrl", None) is None:
            camera: EufySecurityCamera = EufySecurityCamera(
                hass, coordinator, entry, entity
            )
            entities.append(camera)

    _LOGGER.debug(f"{DOMAIN} - camera setup entries - {entities}")
    async_add_devices(entities, True)
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
        self.loop = self.hass.loop
        self.camera_picture_bytes = None
        self.camera_picture_url = None
        self.ffmpeg_binary = self.hass.data[DATA_FFMPEG].binary
        self.ffmpeg = CameraMjpeg(self.ffmpeg_binary)
        self.image_frame = ImageFrame(self.ffmpeg_binary)
        self.serial_number = self.entity["serialNumber"]
        self.ffmpeg_output = f"{DOMAIN}-{self.serial_number}.m3u8"

        self.coordinator.cache[self.serial_number] = {}
        self.cached_entity = self.coordinator.cache[self.serial_number]
        self.properties = self.coordinator.properties[self.serial_number]

        # for p2p streaming
        self.start_stream_function = self.async_start_livestream
        self.stop_stream_function = self.async_stop_livestream
        self.cached_entity["liveStreamingStatus"] = None
        self.cached_entity["queue"] = Queue()
        self.cached_entity["video_codec"] = None

        # for rtsp streaming
        self.cached_entity["rtspUrl"] = None
        if not self.entity.get("rtspStream", None) is None:
            self.start_stream_function = self.async_start_rtsp
            self.stop_stream_function = self.async_stop_rtsp

        self.streaming_source = None
        self.is_streaming = False

    def on_close(self, future="") -> None:
        self.ffmpeg.process.communicate()
        self.ffmpeg.kill()

    @property
    def state(self) -> str:
        prev_is_streaming = self.is_streaming
        if (
            self.entity.get("rtspStream", False) == True
            or self.cached_entity["liveStreamingStatus"] == STATE_LIVE_STREAMING
        ):
            if self.entity.get("rtspStream", False) == True:
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
                f"{DOMAIN} - state change - {prev_is_streaming} {self.is_streaming}"
            )

        if prev_is_streaming == False and self.is_streaming == True:
            async_call_later(self.hass, 0, self.create_stream)
        elif prev_is_streaming == True and self.is_streaming == False:
            self.stream = None
            self.ffmpeg_video_thread.stop()
            self.ffmpeg_image_thread.stop()

        if self.is_streaming:
            return STATE_STREAMING
        elif self.entity.get("motionDetected", False):
            return STATE_MOTION_DETECTED
        elif self.entity.get("personDetected", False):
            return STATE_PERSON_DETECTED
        else:
            if not self.entity.get("battery", None) is None:
                return f"{STATE_IDLE} - {self.entity['battery']} %"
            else:
                return STATE_IDLE

    async def initiate_turn_on(self):
        _LOGGER.debug(f"{DOMAIN} - create_stream - is_streaming - false")
        await self.hass.async_add_executor_job(self.turn_on)
        for counter in range(10):
            _LOGGER.debug(
                f"{DOMAIN} - create_stream - wait for stream start - {counter} - {self.is_streaming}"
            )
            if self.is_streaming == False:
                await asyncio.sleep(1)
            else:
                # camera turn_on was not able to start stream in 10 seconds, let it throw error
                return True
        return False

    async def create_stream(self, executed_at=None) -> Stream:
        _LOGGER.debug(f"{DOMAIN} - create_stream - start")
        if self.is_streaming == False:
            await self.initiate_turn_on()

        _LOGGER.debug(f"{DOMAIN} - create_stream - is_streaming - {self.is_streaming}")
        if self.stream is not None:
            return self.stream

        if self.streaming_source == STREAMING_SOURCE_P2P:
            self.ffmpeg_video_thread = FFMpegVideoHandlerThread(self.hass, self)
            self.ffmpeg_video_thread.start()
            stream_source = self.ffmpeg_output
            _LOGGER.debug(f"{DOMAIN} - create_stream p2p - {stream_source}")

        if self.streaming_source == STREAMING_SOURCE_RTSP:
            stream_source = self.cached_entity["rtspUrl"]
            _LOGGER.debug(f"{DOMAIN} - create_stream rtsp - {stream_source}")

        self.stream = create_stream(
            self.hass, stream_source, options=self.stream_options
        )

        _LOGGER.debug(f"{DOMAIN} - create_stream start process_image - {stream_source}")
        self.ffmpeg_image_thread = FFMpegImageHandlerThread(self.hass, self)
        self.ffmpeg_image_thread.start()
        return self.stream

    def camera_image(self) -> bytes:
        current_picture_url = self.entity.get("pictureUrl", "")
        if self.camera_picture_url != current_picture_url:
            _LOGGER.debug(f"{DOMAIN} - camera_image {current_picture_url}")
            response = requests.get(current_picture_url)
            _LOGGER.debug(
                f"{DOMAIN} - camera_image -{response.status_code} - {len(response.content)}"
            )
            if response.status_code == 200:
                self.camera_picture_url = current_picture_url
                self.camera_picture_bytes = response.content

        return self.camera_picture_bytes

    def turn_on(self) -> None:
        asyncio.run_coroutine_threadsafe(
            self.start_stream_function(),
            self.loop,
        ).result()

    def turn_off(self) -> None:
        asyncio.run_coroutine_threadsafe(
            self.stop_stream_function(),
            self.loop,
        ).result()

    async def async_start_livestream(self) -> None:
        await self.coordinator.async_set_livestream(self.serial_number, "start")

    async def async_stop_livestream(self) -> None:
        await self.coordinator.async_set_livestream(self.serial_number, "stop")

    async def async_start_rtsp(self) -> None:
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
        return self.entity["name"]

    @property
    def brand(self):
        return f"{NAME}"

    @property
    def model(self):
        return self.entity["model"]

    @property
    def is_on(self):
        return self.entity["enabled"]

    @property
    def motion_detection_enabled(self):
        return self.entity.get("motionDetection", False)

    @property
    def state_attributes(self):
        attrs = {}
        attrs["data"] = self.entity
        attrs["live_streaming_status"] = self.cached_entity["liveStreamingStatus"]
        attrs["queue_size"] = self.cached_entity["queue"].qsize()
        attrs["rtsp_url"] = self.cached_entity["rtspUrl"]
        attrs["properties"] = self.properties

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
    def __init__(self, hass, camera: EufySecurityCamera):
        super().__init__()
        self.hass = hass
        self.camera = camera

    def wait_for_video_codec(self):
        for counter in range(10):
            _LOGGER.debug(
                f"{DOMAIN} - thread run - wait for video_codec to arrive - {counter} - {self.camera.cached_entity['video_codec']}"
            )
            if self.camera.cached_entity["video_codec"] is None:
                sleep(0.1)
            else:
                # video codec did not show up in timely manner
                return True
        return False

    def open_ffmpeg(self):
        ffmpeg_command_instance = FFMPEG_COMMAND.copy()
        input_file_index = ffmpeg_command_instance.index("-i")
        video_codec = self.camera.cached_entity["video_codec"]
        if video_codec == "h265":
            video_codec = "hevc"
        ffmpeg_command_instance[input_file_index - 1] = video_codec

        if self.camera.ffmpeg.is_running == False:
            _LOGGER.debug(f"{DOMAIN} - starting ffmpeg")
            asyncio.run_coroutine_threadsafe(
                self.camera.ffmpeg.open(
                    cmd=ffmpeg_command_instance,
                    input_source=None,
                    extra_cmd=FFMPEG_OPTIONS,
                    output=self.camera.ffmpeg_output,
                    stderr_pipe=True,
                    stdout_pipe=False,
                ),
                self.hass.loop,
            ).result()

    def run(self):
        _LOGGER.debug("FFMpegVideoHandlerThread start")
        if self.wait_for_video_codec() == False:
            return

        _LOGGER.debug("FFMpegVideoHandlerThread video codec arrived")
        self.open_ffmpeg()

        _LOGGER.debug("FFMpegVideoHandlerThread ffmpeg is open")
        queue = self.camera.cached_entity["queue"]
        _LOGGER.debug(f"{DOMAIN} - process_frames")
        while True:
            _LOGGER.debug(f"{DOMAIN} - FFMpegVideoHandlerThread size - {queue.qsize()}")
            while not queue.empty():
                try:
                    frame_bytes = bytearray(queue.get().get("data", None))
                    self.camera.ffmpeg.process.stdin.write(frame_bytes)
                except Exception as ex:  # pylint: disable=broad-except
                    _LOGGER.error(
                        f"{DOMAIN} FFMpegVideoHandlerThread exception: {ex}- traceback: {traceback.format_exc()}"
                    )
                    _, ffmpeg_error = self.camera.ffmpeg.process.communicate()
                    if ffmpeg_error is not None:
                        ffmpeg_error = ffmpeg_error.decode()
                        _LOGGER.debug(f"{DOMAIN} - video ffmpeg error - {ffmpeg_error}")

            if self.camera.is_streaming == False:
                return

            _LOGGER.debug(f"{DOMAIN} - process_frames - sleeping")
            sleep(1)

    def stop(self):
        _LOGGER.info("Stopping FFMpegVideoHandlerThread")
        self.camera.cached_entity["queue"].queue.clear()
        self.camera.ffmpeg.process.communicate()
        self.camera.ffmpeg.kill()
        self.join()


class FFMpegImageHandlerThread(threading.Thread):
    def __init__(self, hass, camera: EufySecurityCamera):
        super().__init__()
        self.hass = hass
        self.camera = camera

    def run(self):
        _LOGGER.debug(
            f"{DOMAIN} - FFMpegImageHandlerThread start - {self.camera.stream} {self.camera.is_streaming}"
        )
        while True:
            if self.camera.stream is None or self.camera.is_streaming == False:
                _LOGGER.debug(
                    f"{DOMAIN} - FFMpegImageHandlerThread return - {self.camera.stream} {self.camera.is_streaming}"
                )
                return
            image_frame_bytes = asyncio.run_coroutine_threadsafe(
                self.camera.image_frame.get_image(self.camera.stream.source),
                self.hass.loop,
            ).result()

            if image_frame_bytes is not None:
                _LOGGER.debug(
                    f"{DOMAIN} - FFMpegImageHandlerThread len - {len(image_frame_bytes)}"
                )

            if image_frame_bytes is not None and len(image_frame_bytes) > 0:
                self.camera.camera_picture_bytes = image_frame_bytes
                self.camera.schedule_update_ha_state(False)

            sleep(1)

    def stop(self):
        _LOGGER.info("Stopping FFMpegImageHandlerThread")
        self.camera.ffmpeg.process.communicate()
        self.camera.ffmpeg.kill()
        self.join()
