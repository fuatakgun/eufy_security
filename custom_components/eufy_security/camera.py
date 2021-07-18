import logging

import asyncio
import async_timeout
import requests
import traceback

from haffmpeg.camera import CameraMjpeg
from haffmpeg.tools import IMAGE_JPEG, ImageFrame
from homeassistant.components.camera import Camera
from homeassistant.components.camera import SUPPORT_ON_OFF, SUPPORT_STREAM
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.stream import Stream, create_stream
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN, NAME
from .entity import EufySecurityEntity
from .coordinator import EufySecurityDataUpdateCoordinator

STATE_RECORDING = "recording"
STATE_STREAMING = "streaming"
STATE_IDLE = "idle"
FFMPEG_COMMAND = [
    "-protocol_whitelist",
    "pipe,file,tcp",
    "-f",
    "h264",
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
FFMPEG_OUTPUT = "test.m3u8"


_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass, entry, async_add_devices):
    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN]

    entities = []
    for entity in coordinator.data["data"]["devices"]:
        camera: EufySecurityCamera = EufySecurityCamera(
            hass, coordinator, entry, entity
        )
        entities.append(camera)

    _LOGGER.debug(f"{DOMAIN} - camera setup entries - {entities}")
    async_add_devices(entities, True)


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
        self.coordinator.data["cache"][self.entity["serialNumber"]] = {}
        self.cached_entity = self.coordinator.data["cache"][self.entity["serialNumber"]]
        self.cached_entity["queue"] = []
        self.cached_entity["rtspUrl"] = None
        self.cached_entity["liveStreamingStatus"] = None
        self.live_streaming_status = None
        self.is_streaming = False

    @property
    def id(self):
        return f"{DOMAIN}_{self.entity['serialNumber']}_camera"

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
    def state(self) -> str:
        prev_is_streaming = self.is_streaming
        self.live_streaming_status = self.cached_entity["liveStreamingStatus"]
        if (
            self.entity["rtspStream"] == True
            or self.live_streaming_status == "livestream started"
        ):
            self.is_streaming = True
        else:
            self.is_streaming = False

        if prev_is_streaming == False and self.is_streaming == True:
            _LOGGER.debug(f"{DOMAIN} - state - {prev_is_streaming} {self.is_streaming}")
            async_call_later(self.hass, 0, self.create_stream)
        elif prev_is_streaming == True and self.is_streaming == False:
            _LOGGER.debug(f"{DOMAIN} - state - {prev_is_streaming} {self.is_streaming}")
            self.stream = None

        if self.is_streaming:
            return STATE_STREAMING
        elif self.entity["motionDetected"]:
            return "Motion Detected"
        elif self.entity["personDetected"]:
            return "Person Detected"
        else:
            if not self.entity.get("battery", None) is None:
                return f"Idle - {self.entity.get('battery')} %"
            else:
                return STATE_IDLE

    @property
    def is_on(self):
        return self.entity["enabled"]

    @property
    def motion_detection_enabled(self):
        return self.entity["motionDetection"]

    async def get_ffmpeg(self):
        if self.ffmpeg.is_running == False:
            _LOGGER.debug(f"{DOMAIN} - starting ffmpeg")
            await self.ffmpeg.open(
                cmd=FFMPEG_COMMAND,
                input_source=None,
                extra_cmd=FFMPEG_OPTIONS,
                output=FFMPEG_OUTPUT,
                stderr_pipe=True,
                stdout_pipe=False,
            )

        task = self.loop.create_task(self.process_frames())
        task.add_done_callback(self.on_close)

    def on_close(self, future="") -> None:
        self.ffmpeg.process.communicate()
        self.ffmpeg.kill()

    async def process_frames(self):
        queue = self.cached_entity["queue"]
        _LOGGER.debug(f"{DOMAIN} - process_frames")
        while True:
            _LOGGER.debug(f"{DOMAIN} - process_frames - {len(queue)}")
            while len(queue) > 0:
                try:
                    frame_bytes = bytearray(queue.pop(0).get("data", None))
                    self.ffmpeg.process.stdin.write(frame_bytes)
                except Exception as ex:  # pylint: disable=broad-except
                    _LOGGER.error(
                        f"{DOMAIN} Exception in video : %s - traceback: %s",
                        ex,
                        traceback.format_exc(),
                    )
                    _, ffmpeg_error = self.ffmpeg.process.communicate()
                    if ffmpeg_error is not None:
                        ffmpeg_error = ffmpeg_error.decode()
                        _LOGGER.debug(f"{DOMAIN} - video ffmpeg error - {ffmpeg_error}")

            if self.is_streaming == False:
                return
            await asyncio.sleep(1)

    async def create_stream(self, executed_at=None) -> Stream:
        _LOGGER.debug(f"{DOMAIN} - create_stream - 1")
        if self.is_streaming == False:
            return None

        if self.stream is not None:
            return self.stream

        if self.live_streaming_status == "livestream started":
            await self.get_ffmpeg()
            stream_source = FFMPEG_OUTPUT
            _LOGGER.debug(f"{DOMAIN} - create_stream - 2 - {stream_source}")
        else:
            stream_source = self.cached_entity["rtspUrl"]
            _LOGGER.debug(f"{DOMAIN} - create_stream - 3 - {stream_source}")

        self.stream = create_stream(
            self.hass, stream_source, options=self.stream_options
        )

        self.loop.create_task(self.process_image())

        return self.stream

    async def process_image(self):
        while True:
            if self.stream is None or self.is_streaming == False:
                _LOGGER.debug(
                    f"{DOMAIN} - process_image return - {self.stream} {self.is_streaming}"
                )
                return
            image_frame_bytes = await self.image_frame.get_image(self.stream.source)
            _LOGGER.debug(f"{DOMAIN} - process_image - {len(image_frame_bytes)}")
            if len(image_frame_bytes) > 0:
                self.camera_picture_bytes = image_frame_bytes
            await asyncio.sleep(1)

    def turn_on(self) -> None:
        if self.entity.get("rtspStream", None) is None:
            asyncio.run_coroutine_threadsafe(
                self.coordinator.async_set_livestream(
                    self.entity["serialNumber"], "start"
                ),
                self.loop,
            ).result()
        else:
            asyncio.run_coroutine_threadsafe(
                self.coordinator.async_set_rtsp(self.entity["serialNumber"], True),
                self.loop,
            ).result()

    def turn_off(self) -> None:
        if self.entity.get("rtspStream", None) is None:
            asyncio.run_coroutine_threadsafe(
                self.coordinator.async_set_livestream(
                    self.entity["serialNumber"], "stop"
                ),
                self.loop,
            ).result()
        else:
            asyncio.run_coroutine_threadsafe(
                self.coordinator.async_set_rtsp(self.entity["serialNumber"], False),
                self.loop,
            ).result()

    def camera_image(self) -> bytes:
        if self.camera_picture_url != self.entity["pictureUrl"]:
            _LOGGER.debug(f"{DOMAIN} - camera_image {self.entity['pictureUrl']}")
            response = requests.get(self.entity["pictureUrl"])
            _LOGGER.debug(
                f"{DOMAIN} - camera_image -{response.status_code} - {len(response.content)}"
            )
            if response.status_code == 200:
                self.camera_picture_url = self.entity["pictureUrl"]
                self.camera_picture_bytes = response.content

        return self.camera_picture_bytes

    @property
    def state_attributes(self):
        attrs = {}
        attrs["data"] = self.entity
        attrs["live_streaming_status"] = self.cached_entity["liveStreamingStatus"]
        attrs["queue_size"] = len(self.cached_entity["queue"])

        attrs["rtsp_url"] = self.cached_entity["rtspUrl"]

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
