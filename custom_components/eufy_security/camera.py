import logging

import asyncio
import datetime
from datetime import timedelta
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later, async_track_state_change, async_track_time_interval
from homeassistant.helpers import config_validation as cv, entity_platform, service
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, NAME, START_LIVESTREAM_AT_INITIALIZE
from .const import wait_for_value
from .entity import EufySecurityEntity
from .coordinator import EufySecurityDataUpdateCoordinator
from time import sleep

STATE_IDLE = "Idle"
STATE_STREAM_INITIALIZING = "Stream Initializing"
STATE_STREAMING = "Streaming"
STATE_MOTION_DETECTED = "Motion Detected"
STATE_PERSON_DETECTED = "Person Detected"
STATE_LIVE_STREAMING = "livestream started"
STREAMING_SOURCE_RTSP = "rtsp"
STREAMING_SOURCE_P2P = "p2p"
FFMPEG_COMMAND = [
    "-y",
    # "-probesize", "128",
    # "-analyzeduration", "0",
    "-protocol_whitelist", "pipe,file,tcp",
    "-f", "{video_codec}",
    "-i", "-",
    "-vcodec", "copy",
    "-protocol_whitelist", "pipe,file,tcp,udp,rtsp,rtp",
]
FFMPEG_OPTIONS = (
    " -hls_init_time 2"
    " -hls_time 2"
    " -hls_segment_type mpegts"
    " -hls_playlist_type event "
    " -hls_list_size 5"
    " -preset ultrafast"
    " -absf aac_adtstoasc"
    " -g 15"
    " -sc_threshold 0"
    " -fflags genpts+nobuffer+flush_packets"
    " -loglevel debug"
    " -report"
)

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_devices):
    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN]

    # if device type is CAMERA or DOORBELL, create corresponding camera entities and add
    entities = []
    for entity in coordinator.state["devices"]:
        if entity["category"] in ["CAMERA", "DOORBELL"]:
            camera: EufySecurityCamera = EufySecurityCamera(hass, coordinator, entry, entity)
            entities.append(camera)

    _LOGGER.debug(f"{DOMAIN} - camera setup entries - {entities}")
    async_add_devices(entities, True)

    # register entity level services
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service("start_livestream", {}, "async_start_livestream")
    platform.async_register_entity_service("stop_livestream", {}, "async_stop_livestream")
    platform.async_register_entity_service("start_rtsp", {}, "async_start_rtsp")
    platform.async_register_entity_service("stop_rtsp", {}, "async_stop_rtsp")
    platform.async_register_entity_service("enable", {}, "async_enable")
    platform.async_register_entity_service("disable", {}, "async_disable")


class EufySecurityCamera(EufySecurityEntity, Camera):
    def __init__(self, hass: HomeAssistant, coordinator: EufySecurityDataUpdateCoordinator, entry: ConfigEntry, entity: dict):
        EufySecurityEntity.__init__(self, coordinator, entry, entity)
        Camera.__init__(self)
        self.hass: HomeAssistant = hass
        self.coordinator: EufySecurityDataUpdateCoordinator = coordinator
        self.entity = entity

        # initialize values
        self.serial_number = self.entity["serialNumber"]
        self.coordinator.cache[self.serial_number] = {}
        self.cached_entity = self.coordinator.cache[self.serial_number]
        self.properties = self.coordinator.properties[self.serial_number]

        # camera image
        self.picture_bytes = None
        self.picture_url = None

        # for p2p streaming
        self.start_stream_function = self.async_start_livestream
        self.stop_stream_function = self.async_stop_livestream
        self.cached_entity["liveStreamingStatus"] = None
        self.cached_entity["queue"] = Queue()
        self.cached_entity["latest_codec"] = None
        self.queue: Queue = self.cached_entity["queue"]
        self.p2p_thread = None
        self.empty_queue_counter = 0

        # video generation using ffmpeg for p2p
        self.ffmpeg_binary = self.hass.data[DATA_FFMPEG].binary
        self.ffmpeg = CameraMjpeg(self.ffmpeg_binary)
        self.default_codec = "h264"

        self.ffmpeg_output = f"{DOMAIN}-{self.serial_number}"
        if self.coordinator.use_rtsp_server_addon == True:
            self.p2p_url = f"rtsp://{self.coordinator.ws.host}:8554/{self.ffmpeg_output}"
            self.ffmpeg_output = f"-f rtsp -rtsp_transport tcp {self.p2p_url}"
        else:
            self.ffmpeg_output = f"{self.ffmpeg_output}.m3u8"
            self.p2p_url = self.ffmpeg_output

        # when HA started, p2p streaming was active, we need to catch up
        if self.entity.get(START_LIVESTREAM_AT_INITIALIZE, False) == True:
            async_call_later(self.hass, 0, self.async_start_livestream)

        # for rtsp streaming
        self.cached_entity["rtspUrl"] = None
        if not self.entity.get("rtspStream", None) is None:
            self.start_stream_function = self.async_start_rtsp
            self.stop_stream_function = self.async_stop_rtsp

        # when HA started, if rtsp streaming was active, we need to catch up
        if self.entity.get("rtspStream", False) == True:
            if self.cached_entity["rtspUrl"] is None:
                async_call_later(self.hass, 0, self.async_start_rtsp)

        self.stream_source_type = None
        self.stream_source_address = None
        self.is_streaming = False

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.hass.bus.async_listen(f"{DOMAIN}_{self.serial_number}_event_received", self.handle_incoming_video_data)

    async def handle_incoming_video_data(self, event):
        lock = asyncio.Lock()
        async with lock:
            if self.cached_entity['latest_codec'] != self.default_codec:
                _LOGGER.debug(f"{DOMAIN} {self.name} - set codec - default {self.default_codec} - incoming {self.cached_entity['latest_codec']}")
                self.default_codec = self.cached_entity['latest_codec']
                await self.hass.async_add_executor_job(self.stop_ffmpeg)
                await self.open_ffmpeg()
        data = event.data
        self.queue.put(data)

    def stop_ffmpeg(self):
        try:
            _LOGGER.debug(f"{DOMAIN} {self.name} - stop_ffmpeg - 1")
            self.ffmpeg.process.stdin.write(b"q")
            _LOGGER.debug(f"{DOMAIN} {self.name} - stop_ffmpeg - 2")
            self.ffmpeg.process.communicate()
            _LOGGER.debug(f"{DOMAIN} {self.name} - stop_ffmpeg - 3")
            self.ffmpeg.kill()
            _LOGGER.debug(f"{DOMAIN} {self.name} - stop_ffmpeg - 4")
            self.ffmpeg._argv = None
            _LOGGER.debug(f"{DOMAIN} {self.name} - stop_ffmpeg - 5")
            self.ffmpeg._proc = None
            _LOGGER.debug(f"{DOMAIN} {self.name} - stop_ffmpeg - 6")
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error(f"{DOMAIN} {self.name} - stop_ffmpeg exception: {ex}- traceback: {traceback.format_exc()}")
        _LOGGER.debug(f"{DOMAIN} {self.name} - stop_ffmpeg - done")

    def write_to_stdin(self,frame_bytes):
        if self.ffmpeg.is_running == True:
            try:
                self.ffmpeg.process.stdin.write(frame_bytes)
            except:
                pass

    def handle_queue_threaded(self):
        _LOGGER.debug(f"{DOMAIN} {self.name} - handle_queue_threaded - start - {self.queue.qsize()} - {self.ffmpeg.is_running}")

        while self.empty_queue_counter < 10 and self.is_streaming == True:
            _LOGGER.debug(f"{DOMAIN} {self.name} - handle_queue_threaded - writing size and state - {self.queue.qsize()} - {self.ffmpeg.is_running}")
            if self.queue.empty() == True or self.ffmpeg.is_running == False:
                self.empty_queue_counter = self.empty_queue_counter + 1
                sleep(0.5)

            while not self.queue.empty():
                self.empty_queue_counter = 0
                data = self.queue.get()
                frame_bytes = bytearray(data["data"])
                if not frame_bytes is None:
                    try:
                        self.write_to_stdin(frame_bytes)
                    except Exception as ex:  # pylint: disable=broad-except
                        _LOGGER.error(f"{DOMAIN} {self.name} video_thread exception: {ex}- traceback: {traceback.format_exc()}")
                        _, ffmpeg_error = self.ffmpeg.process.communicate()
                        if ffmpeg_error is not None:
                            ffmpeg_error = ffmpeg_error.decode()
                            _LOGGER.debug(f"{DOMAIN} {self.name} - video ffmpeg error - {ffmpeg_error}")
            sleep(0.5)

        if self.empty_queue_counter >= 10 and self.is_streaming == True:
            asyncio.run_coroutine_threadsafe(self.async_stop_livestream(), self.hass.loop).result()
            return

    @property
    def state(self) -> str:
        self.set_is_streaming()
        if self.is_streaming:
            if not self.stream_source_type is None:
                return f"{STATE_STREAMING} - {self.stream_source_type}"
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
        if (self.entity.get("rtspStream", False) == True or self.cached_entity["liveStreamingStatus"] == STATE_LIVE_STREAMING):
            _LOGGER.debug(f"{DOMAIN} {self.name} - set_is_streaming - something streaming")
            _LOGGER.debug(f"{DOMAIN} {self.name} - set_is_streaming - rtspStream - {self.entity.get('rtspStream', False)}")
            _LOGGER.debug(f"{DOMAIN} {self.name} - set_is_streaming - rtspStream - {self.cached_entity['rtspUrl']}")
            if self.entity.get("rtspStream", False) == True:
                if self.cached_entity["rtspUrl"]:
                    self.stream_source_type = STREAMING_SOURCE_RTSP
                    self.stream_source_address = self.cached_entity["rtspUrl"]
                    self.is_streaming = True
            if self.cached_entity["liveStreamingStatus"] == STATE_LIVE_STREAMING:
                self.stream_source_type = STREAMING_SOURCE_P2P
                self.stream_source_address = self.p2p_url
                self.is_streaming = True
        else:
            self.stream_source_type = None
            self.stream_source_address = None
            self.is_streaming = False

        if prev_is_streaming != self.is_streaming:
            _LOGGER.debug(f"{DOMAIN} {self.name} - state change - {prev_is_streaming} {self.is_streaming}")
            async_call_later(self.hass, 0, self.state_changed)

    async def open_ffmpeg(self):
        _LOGGER.debug(f"{DOMAIN} {self.name} - open_ffmpeg 1 - codec {self.default_codec}")
        ffmpeg_command_instance = FFMPEG_COMMAND.copy()
        _LOGGER.debug(f"{DOMAIN} {self.name} - open_ffmpeg 2 - ffmpeg_command_instance {ffmpeg_command_instance}")
        input_index = ffmpeg_command_instance.index("-i")
        _LOGGER.debug(f"{DOMAIN} {self.name} - open_ffmpeg 3 - ffmpeg_command_instance {ffmpeg_command_instance}")
        ffmpeg_command_instance[input_index - 1] = self.default_codec
        _LOGGER.debug(f"{DOMAIN} {self.name} - open_ffmpeg 4 - ffmpeg_command_instance {ffmpeg_command_instance}")
        result = await self.ffmpeg.open(cmd=ffmpeg_command_instance, input_source=None, extra_cmd=FFMPEG_OPTIONS, output=self.ffmpeg_output, stderr_pipe=False, stdout_pipe=False)
        _LOGGER.debug(f"{DOMAIN} {self.name} - open_ffmpeg 5 - ffmpeg_command_instance {ffmpeg_command_instance}")
        return result

    async def state_changed(self, executed_at=None):
        prev_is_streaming = not self.is_streaming
        if prev_is_streaming == False and self.is_streaming == True:
            if self.stream_source_type == STREAMING_SOURCE_P2P:
                self.queue.queue.clear()
                if self.ffmpeg.is_running == True:
                    _LOGGER.error(f"{DOMAIN} {self.name} - state_changed - ffmeg - running")
                    await self.hass.async_add_executor_job(self.stop_ffmpeg)
                await self.open_ffmpeg()
                _LOGGER.debug(f"{DOMAIN} {self.name} - state_changed - ffmpeg - done - {self.ffmpeg_output}")
                self.empty_queue_counter = 0
                self.p2p_thread = threading.Thread(target=self.handle_queue_threaded, daemon=True)
                self.p2p_thread.start()
        elif prev_is_streaming == True and self.is_streaming == False:
            # streaming has finished, destroy stream
            if not self.stream is None:
                await self.hass.async_add_executor_job(self.stream.stop)
                self.stream = None
            if self.ffmpeg.is_running == True:
                await self.hass.async_add_executor_job(self.stop_ffmpeg)
            if not self.p2p_thread is None:
                self.p2p_thread = None
            self.empty_queue_counter = 0

    async def initiate_turn_on(self):
        await self.hass.async_add_executor_job(self.turn_on)
        return await wait_for_value(self.__dict__, "is_streaming", False, interval=0.5)

    async def stream_source(self):
        _LOGGER.debug(f"{DOMAIN} {self.name} - stream_source")
        if self.is_streaming == False:
            await self.initiate_turn_on()
        return self.stream_source_address

    def camera_image(self) -> bytes:
        return asyncio.run_coroutine_threadsafe(self.async_camera_image(), self.hass.loop).result()

    async def async_camera_image(self) -> bytes:
        # if streaming is active, do not overwrite live image
        if self.is_streaming == True:
            image_frame_bytes = await ImageFrame(self.ffmpeg_binary).get_image(self.stream_source_address)
            if image_frame_bytes is not None and len(image_frame_bytes) > 0:
                _LOGGER.debug(f"{DOMAIN} {self.name} - camera_image len - {len(image_frame_bytes)}")
                self.picture_bytes = image_frame_bytes
        else:
            current_picture_url = self.entity.get("pictureUrl", "")
            if self.picture_url != current_picture_url:
                async with async_get_clientsession(self.hass).get(current_picture_url) as response:
                    if response.status == 200:
                        self.picture_bytes = await response.read()
                        self.picture_url = current_picture_url
                        _LOGGER.debug(f"{DOMAIN} {self.name} - camera_image -{current_picture_url} - {len(self.picture_bytes)}")
        return self.picture_bytes

    def turn_on(self) -> None:
        asyncio.run_coroutine_threadsafe(self.start_stream_function(), self.hass.loop).result()

    def turn_off(self) -> None:
        asyncio.run_coroutine_threadsafe(self.stop_stream_function(), self.hass.loop).result()

    async def async_start_livestream(self, executed_at=None) -> None:
        await self.coordinator.async_set_livestream(self.serial_number, "start")

    async def async_stop_livestream(self) -> None:
        await self.coordinator.async_set_livestream(self.serial_number, "stop")

    async def async_start_rtsp(self, executed_at=None) -> None:
        await self.coordinator.async_set_rtsp(self.serial_number, True)
        await asyncio.sleep(1)
        dummy = self.state


    async def async_stop_rtsp(self) -> None:
        await self.coordinator.async_set_rtsp(self.serial_number, False)
        await asyncio.sleep(1)
        dummy = self.state

    async def async_enable(self) -> None:
        await self.coordinator.async_set_device_state(self.serial_number, True)

    async def async_disable(self) -> None:
        await self.coordinator.async_set_device_state(self.serial_number, False)

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
        attrs["debug"]["stream_source_type"] = self.stream_source_type
        attrs["debug"]["stream_source_address"] = self.stream_source_address
        attrs["debug"]["p2p_streaming_response"] = self.cached_entity["liveStreamingStatus"]
        attrs["debug"]["queue_size"] = self.queue.qsize()
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