import logging

import asyncio
import requests

from homeassistant.components.camera import Camera
from homeassistant.components.camera import SUPPORT_ON_OFF, SUPPORT_STREAM
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, NAME
from .entity import EufySecurityEntity
from .coordinator import EufySecurityDataUpdateCoordinator

STATE_RECORDING = "recording"
STATE_STREAMING = "streaming"
STATE_IDLE = "idle"


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
        self.camera_picture_bytes = None
        self.camera_picture_url = None

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
        self.is_streaming = self.entity["rtspStream"]
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

    async def stream_source(self):
        if self.is_streaming == False:
            return None
        cached_entity = self.coordinator.data["cache"].get(
            self.entity["serialNumber"], None
        )
        if cached_entity is not None:
            self._stream_source = cached_entity.get("rtspUrl", None)
        return self._stream_source

    def turn_on(self) -> None:
        asyncio.run_coroutine_threadsafe(
            self.coordinator.async_set_rtsp(self.entity["serialNumber"], True),
            self.hass.loop,
        ).result()

    def turn_off(self) -> None:
        asyncio.run_coroutine_threadsafe(
            self.coordinator.async_set_rtsp(self.entity["serialNumber"], False),
            self.hass.loop,
        ).result()

    def camera_image(self) -> bytes:
        if (
            self.camera_picture_bytes is None
            or self.camera_picture_url is None
            or self.camera_picture_url != self.entity["pictureUrl"]
        ):
            # cachine of image
            _LOGGER.debug(f"{DOMAIN} - camera_image {self.entity['pictureUrl']}")
            response = requests.get(self.entity["pictureUrl"])
            if response.status_code != 200:
                return None
            self.camera_picture_url = self.entity["pictureUrl"]
            self.camera_picture_bytes = response.content
        return self.camera_picture_bytes

    @property
    def state_attributes(self):
        attrs = self.entity

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
