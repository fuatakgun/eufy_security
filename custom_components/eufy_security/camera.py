import logging

import asyncio
import time
import traceback
from queue import Queue
import threading
import os

from time import sleep

from haffmpeg.camera import CameraMjpeg
from haffmpeg.tools import ImageFrame
from homeassistant.components.camera import Camera
from homeassistant.components.camera import SUPPORT_ON_OFF, SUPPORT_STREAM
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.stream import Stream, create_stream
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import COORDINATOR, DEFAULT_CODEC, DOMAIN, NAME, Device
from .const import wait_for_value
from .entity import EufySecurityEntity
from .coordinator import EufySecurityDataUpdateCoordinator

STATE_IDLE = "Idle"
STATE_STREAMING = "Streaming"
STATE_MOTION_DETECTED = "Motion Detected"
STATE_PERSON_DETECTED = "Person Detected"

STREAMING_SOURCE_RTSP = "rtsp"
STREAMING_SOURCE_P2P = "p2p"

FFMPEG_COMMAND = [
    "-re",
    "-y",
    "-analyzeduration", "{analyze_duration}",
    "-protocol_whitelist", "pipe,file,tcp",
    "-f", "{video_codec}",
    "-i", "-",
    "-vcodec", "copy",
    "-protocol_whitelist", "pipe,file,tcp,udp,rtsp,rtp",
]
FFMPEG_OPTIONS = (
    " -hls_init_time 1"
    " -hls_time 1"
    " -hls_segment_type mpegts"
    " -hls_playlist_type event "
    " -hls_list_size 2"
    " -preset ultrafast"
    " -tune zerolatency"
    " -g 15"
    " -sc_threshold 0"
    " -fflags genpts+nobuffer+flush_packets"
    " -loglevel debug"
    " -report"
)

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_devices):
    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN][COORDINATOR]

    entities = []
    for device in coordinator.devices.values():
        if device.is_camera() == True:
            camera: EufySecurityCamera = EufySecurityCamera(coordinator, config_entry, device)
            entities.append(camera)

    _LOGGER.debug(f"{DOMAIN} - camera setup entries - {entities}")
    async_add_devices(entities, True)

    # register entity level services
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service("start_livestream", {}, "async_start_p2p_livestream")
    platform.async_register_entity_service("stop_livestream", {}, "async_stop_p2p_livestream")
    platform.async_register_entity_service("start_p2p_livestream", {}, "async_start_p2p_livestream")
    platform.async_register_entity_service("stop_p2p_livestream", {}, "async_stop_p2p_livestream")
    platform.async_register_entity_service("start_rtsp_livestream", {}, "async_start_rtsp_livestream")
    platform.async_register_entity_service("stop_rtsp_livestream", {}, "async_stop_rtsp_livestream")
    platform.async_register_entity_service("enable_rtsp", {}, "async_enable_rtsp")
    platform.async_register_entity_service("disable_rtsp", {}, "async_disable_rtsp")
    platform.async_register_entity_service("enable", {}, "async_enable")
    platform.async_register_entity_service("disable", {}, "async_disable")

class EufySecurityCamera(EufySecurityEntity, Camera):
    def __init__(self, coordinator: EufySecurityDataUpdateCoordinator, config_entry: ConfigEntry, device: Device):
        EufySecurityEntity.__init__(self, coordinator, config_entry, device)
        Camera.__init__(self)

        self.device.set_streaming_status_callback(self.set_is_streaming)

        # camera image
        self.picture_bytes = None
        self.picture_url = None

        # p2p streaming
        self.start_stream_function = self.async_start_p2p_livestream
        self.stop_stream_function = self.async_stop_p2p_livestream

        # video generation using ffmpeg for p2p
        self.ffmpeg_binary = self.coordinator.hass.data[DATA_FFMPEG].binary
        self.ffmpeg = CameraMjpeg(self.ffmpeg_binary)
        self.default_codec = DEFAULT_CODEC
        self.is_ffmpeg_running = False

        # when HA started, p2p streaming was active, catch up with p2p streaming
        if self.device.is_p2p_streaming == True:
            async_call_later(self.coordinator.hass, 0, self.async_start_p2p_livestream)

        if self.coordinator.config.use_rtsp_server_addon == True:
            self.p2p_url = f"rtsp://{self.coordinator.config.rtsp_server_address}:{self.coordinator.config.rtsp_server_port}/{self.device.serial_number}"
            self.ffmpeg_output = f"-f rtsp -rtsp_transport tcp {self.p2p_url}"
        else:
            self.ffmpeg_output = f"{DOMAIN}-{self.device.serial_number}.m3u8"
            self.p2p_url = self.ffmpeg_output

        # for rtsp streaming
        if not self.device.state.get("rtspStream", None) is None:
            self.start_stream_function = self.async_start_rtsp_livestream
            self.stop_stream_function = self.async_stop_rtsp_livestream

        self.set_is_streaming()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.coordinator.hass.bus.async_listen(f"{DOMAIN}_{self.device.serial_number}_event_received", self.handle_incoming_video_data)

    async def check_and_set_codec(self):
        if self.device.codec != self.default_codec:
            _LOGGER.debug(f"{DOMAIN} {self.name} - set codec - default {self.default_codec} - incoming {self.device.codec}")
            self.default_codec = self.device.codec
            await self.coordinator.hass.async_add_executor_job(self.stop_ffmpeg)
            await self.start_ffmpeg()

    async def handle_incoming_video_data(self, event):
        await self.check_and_set_codec()
        self.device.queue.put(event.data)

    def handle_queue_threaded(self):
        sleep_duration = 0.1
        _LOGGER.debug(f"{DOMAIN} {self.name} - handle_queue_threaded - start - {self.device.queue.qsize()} - {self.ffmpeg.is_running} - {self.device.is_streaming}")
        for i in range(0,10):
            if self.ffmpeg.is_running == False:
                sleep(sleep_duration)

        while self.ffmpeg.is_running == True and self.device.is_streaming == True:
            _LOGGER.debug(f"{DOMAIN} {self.name} - handle_queue_threaded - while - {self.device.queue.qsize()} - {self.ffmpeg.is_running} - {self.device.is_streaming}")
            while not self.device.queue.empty():
                self.write_bytes_to_ffmeg(bytearray(self.device.queue.get()["data"]))
            sleep(sleep_duration)
        _LOGGER.debug(f"{DOMAIN} {self.name} - handle_queue_threaded - finish - {self.device.queue.qsize()} - {self.ffmpeg.is_running} - {self.device.is_streaming}")

    def write_bytes_to_ffmeg(self, frame_bytes):
        if self.ffmpeg.is_running == True:
            try:
                self.ffmpeg.process.stdin.write(frame_bytes)
            except Exception as ex:
                _LOGGER.error(f"{DOMAIN} {self.name} video_thread exception: {ex}- traceback: {traceback.format_exc()}")
                _, ffmpeg_error = self.ffmpeg.process.communicate()
                if ffmpeg_error is not None:
                    ffmpeg_error = ffmpeg_error.decode()
                    _LOGGER.debug(f"{DOMAIN} {self.name} - video ffmpeg error - {ffmpeg_error}")
        else:
            _LOGGER.error(f"{DOMAIN} {self.name} - video ffmpeg error - ffmpeg is not running")

    async def start_ffmpeg(self, executed_at=None):
        _LOGGER.debug(f"{DOMAIN} {self.name} - start_ffmpeg 1 - codec {self.default_codec}")
        ffmpeg_command_instance = FFMPEG_COMMAND.copy()
        input_index = ffmpeg_command_instance.index("-i")
        ffmpeg_command_instance[input_index - 1] = self.default_codec
        ffmpeg_command_instance[input_index - 5] = str(int(self.coordinator.config.ffmpeg_analyze_duration) * 1000000)
        _LOGGER.debug(f"{DOMAIN} {self.name} - start_ffmpeg 2 - ffmpeg_command_instance {ffmpeg_command_instance}")
        result = await self.ffmpeg.open(cmd=ffmpeg_command_instance, input_source=None, extra_cmd=FFMPEG_OPTIONS, output=self.ffmpeg_output, stderr_pipe=False, stdout_pipe=False)
        _LOGGER.debug(f"{DOMAIN} {self.name} - start_ffmpeg 3 - ffmpeg_command_instance {ffmpeg_command_instance}")
        self.is_ffmpeg_running = True
        return result

    def stop_ffmpeg(self):
        try:
            self.ffmpeg.kill()
        except Exception as ex:
            _LOGGER.error(f"{DOMAIN} {self.name} - stop_ffmpeg exception: {ex} - traceback: {traceback.format_exc()}")
        self.is_ffmpeg_running = False
        _LOGGER.debug(f"{DOMAIN} {self.name} - stop_ffmpeg - done")

    def start_p2p(self):
        _LOGGER.debug(f"{DOMAIN} {self.name} - start_p2p - 1")
        self.device.queue.queue.clear()
        self.empty_queue_counter = 0
        if self.ffmpeg.is_running == True:
            _LOGGER.debug(f"{DOMAIN} {self.name} - start_p2p - ffmeg - running - stop it")
            self.stop_ffmpeg()
        _LOGGER.debug(f"{DOMAIN} {self.name} - start_p2p - 2")
        async_call_later(self.coordinator.hass, 0, self.start_ffmpeg)
        # asyncio.run_coroutine_threadsafe(wait_for_value(self.__dict__, "is_ffmpeg_running", False), self.coordinator.hass.loop).result()
        _LOGGER.debug(f"{DOMAIN} {self.name} - start_p2p - 3")
        self.p2p_thread = threading.Thread(target=self.handle_queue_threaded, daemon=True)
        self.p2p_thread.start()

    def stop_p2p(self):
        self.device.queue.queue.clear()
        if not self.stream is None:
            self.stream.stop()
            self.stream = None
        if self.ffmpeg.is_running == True:
            self.stop_ffmpeg()
        self.p2p_thread = None
        self.empty_queue_counter = 0

    @property
    def state(self) -> str:
        if self.device.is_streaming == True:
            return f"{STATE_STREAMING} - {self.device.stream_source_type}"
        elif self.device.state.get("motionDetected", False):
            return STATE_MOTION_DETECTED
        elif self.device.state.get("personDetected", False):
            return STATE_PERSON_DETECTED
        else:
            if not self.device.state.get("battery", None) is None:
                return f"{STATE_IDLE} - {self.device.state['battery']} %"
            return STATE_IDLE

    def set_is_streaming(self):
        _LOGGER.debug(f"{DOMAIN} {self.name} - set_is_streaming - start - {self.device.is_rtsp_streaming} - {self.device.is_p2p_streaming} - {self.device.is_streaming}")
        # based on streaming options, set streaming variables
        if (self.device.is_rtsp_streaming == True or self.device.is_p2p_streaming == True) and self.device.is_streaming == False:
            _LOGGER.debug(f"{DOMAIN} {self.name} - set_is_streaming - some streaming")
            if self.device.is_rtsp_streaming == True:
                self.device.stream_source_type = STREAMING_SOURCE_RTSP
                self.device.stream_source_address = self.device.state["rtspStreamUrl"]
                self.device.is_streaming = True
                _LOGGER.debug(f"{DOMAIN} {self.name} - set_is_streaming - is_rtsp_streaming")
            if self.device.is_p2p_streaming == True:
                self.device.stream_source_type = STREAMING_SOURCE_P2P
                self.device.stream_source_address = self.p2p_url
                self.start_p2p()
                self.device.is_streaming = True
                _LOGGER.debug(f"{DOMAIN} {self.name} - set_is_streaming - is_p2p_streaming")
        if (self.device.is_rtsp_streaming == False and self.device.is_p2p_streaming == False) and self.device.is_streaming == True:
            if self.device.stream_source_type == STREAMING_SOURCE_P2P:
                self.stop_p2p()
            self.device.stream_source_type = None
            self.device.stream_source_address = None
            self.device.is_streaming = False
            _LOGGER.debug(f"{DOMAIN} {self.name} - set_is_streaming - no_streaming")
        _LOGGER.debug(f"{DOMAIN} {self.name} - set_is_streaming - end - {self.device.is_rtsp_streaming} - {self.device.is_p2p_streaming} - {self.device.is_streaming}")

    async def initiate_turn_on(self):
        await self.coordinator.hass.async_add_executor_job(self.turn_on)
        await wait_for_value(self.device.__dict__, "is_streaming", False, interval=0.5)

    async def stream_source(self):
        if self.device.is_streaming == False:
            _LOGGER.debug(f"{DOMAIN} {self.name} - stream_source - start - {self.device.is_streaming}")
            if self.coordinator.config.auto_start_stream == False:
                return None
            await self.initiate_turn_on()
            _LOGGER.debug(f"{DOMAIN} {self.name} - stream_source - initiate finished")
        _LOGGER.debug(f"{DOMAIN} {self.name} - stream_source - address - {self.device.stream_source_address}")
        if self.device.is_streaming == False:
            return None
        return self.device.stream_source_address

    def camera_image(self, width=None, height=None) -> bytes:
        return asyncio.run_coroutine_threadsafe(self.async_camera_image(width, height), self.coordinator.hass.loop).result()

    async def async_camera_image(self, width=None, height=None) -> bytes:
        # if streaming is active, do not overwrite live image
        if self.device.is_streaming == True:
            size_command = None
            if width and height:
                size_command = f"-s {width}x{height}"
            image_frame_bytes = await ImageFrame(self.ffmpeg_binary).get_image(self.device.stream_source_address, extra_cmd = size_command)
            if (not image_frame_bytes is None) and len(image_frame_bytes) > 0:
                _LOGGER.debug(f"{DOMAIN} {self.name} - camera_image len - {len(image_frame_bytes)}")
                self.picture_bytes = image_frame_bytes
                self.picture_url = None
            else:
                if self.device.is_p2p_streaming == True:
                    await self.async_stop_p2p_livestream()
                if self.device.is_rtsp_streaming == True:
                    await self.async_stop_rtsp_livestream()
        else:
            current_picture_url = self.device.state.get("pictureUrl", "")
            if self.picture_url != current_picture_url:
                async with async_get_clientsession(self.coordinator.hass).get(current_picture_url) as response:
                    if response.status == 200:
                        self.picture_bytes = await response.read()
                        self.picture_url = current_picture_url
                        _LOGGER.debug(f"{DOMAIN} {self.name} - camera_image -{current_picture_url} - {len(self.picture_bytes)}")
        return self.picture_bytes

    def turn_on(self) -> None:
        asyncio.run_coroutine_threadsafe(self.start_stream_function(), self.coordinator.hass.loop).result()

    def turn_off(self) -> None:
        asyncio.run_coroutine_threadsafe(self.stop_stream_function(), self.coordinator.hass.loop).result()

    async def check_and_notify_rtsp_enabled(self):
        if self.device.state.get("rtspStream") == False:
            self.coordinator.hass.components.persistent_notification.async_create(
                f"RSTP needs to enabled for Camera {self.device.name}",
                title="Eufy Security - Not Enabled - RTSP",
                notification_id="eufy_security_not_enabled_rtsp",
            )
            return False
        return True

    async def check_and_notify_rtsp_supported(self):
        if self.device.state.get("rtspStream", None) is None:
            self.coordinator.hass.components.persistent_notification.async_create(
                f"Camera {self.device.name} does not support RTSP",
                title="Eufy Security - Not Supported - RTSP",
                notification_id="eufy_security_not_supported_rtsp",
            )
            return False
        return True

    async def async_start_p2p_livestream(self, executed_at=None) -> None:
        await self.coordinator.async_set_p2p_livestream(self.device.serial_number, "start")

    async def async_stop_p2p_livestream(self) -> None:
        await self.coordinator.async_set_p2p_livestream(self.device.serial_number, "stop")

    async def async_start_rtsp_livestream(self, executed_at=None) -> None:
        if await self.check_and_notify_rtsp_supported() == True and await self.check_and_notify_rtsp_enabled():
            await self.coordinator.async_set_rtsp_livestream(self.device.serial_number, "start")

    async def async_stop_rtsp_livestream(self) -> None:
        if await self.check_and_notify_rtsp_supported() == True and await self.check_and_notify_rtsp_enabled():
            await self.coordinator.async_set_rtsp_livestream(self.device.serial_number, "stop")

    async def async_enable_rtsp(self) -> None:
        if await self.check_and_notify_rtsp_supported() == True:
            await self.coordinator.async_set_rtsp(self.device.serial_number, True)

    async def async_disable_rtsp(self) -> None:
        if await self.check_and_notify_rtsp_supported() == True:
            await self.coordinator.async_set_rtsp(self.device.serial_number, False)

    async def async_enable(self) -> None:
        await self.coordinator.async_set_device_state(self.device.serial_number, True)

    async def async_disable(self) -> None:
        await self.coordinator.async_set_device_state(self.device.serial_number, False)

    async def async_get_rtsp_livestream_status(self) -> None:
        await self.coordinator.async_get_rtsp_livestream_status(self.device.serial_number)

    async def async_get_p2p_livestream_status(self) -> None:
        await self.coordinator.async_get_p2p_livestream_status(self.device.serial_number)

    @property
    def id(self):
        return f"{DOMAIN}_{self.device.serial_number}_camera"

    @property
    def unique_id(self):
        return self.id

    @property
    def name(self):
        return self.device.name

    @property
    def brand(self):
        return f"{NAME}"

    @property
    def model(self):
        return self.device.model

    @property
    def is_on(self):
        return self.device.state.get("enabled", True)

    @property
    def motion_detection_enabled(self):
        return self.device.state.get("motionDetection", False)

    @property
    def state_attributes(self):
        return {
            "inherited": super().state_attributes,
            "custom": {
                "is_streaming": self.device.is_streaming,
                "stream_source_type": self.device.stream_source_type,
                "stream_source_address": self.device.stream_source_address,
                "codec": self.device.codec,
                "is_rtsp_streaming": self.device.is_rtsp_streaming,
                "is_p2p_streaming": self.device.is_p2p_streaming,
            }
        }

    @property
    def supported_features(self) -> int:
        return SUPPORT_ON_OFF | SUPPORT_STREAM
