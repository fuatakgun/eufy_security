from __future__ import annotations

import asyncio
import logging

from haffmpeg.camera import CameraMjpeg
import voluptuous as vol

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.aiohttp_client import (
    async_aiohttp_proxy_stream,
    async_get_clientsession,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import COORDINATOR, DOMAIN, Schema
from .coordinator import EufySecurityDataUpdateCoordinator
from .entity import EufySecurityEntity
from .eufy_security_api.camera import StreamProvider, StreamStatus
from .eufy_security_api.metadata import Metadata
from .eufy_security_api.util import get_child_value, wait_for_value_to_equal

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Setup camera entities."""
    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN][COORDINATOR]
    product_properties = []
    for product in coordinator.api.devices.values():
        if product.is_camera is True:
            product_properties.append(Metadata.parse(product, {"name": "camera", "label": "Caamera"}))

    entities = [EufySecurityCamera(coordinator, metadata) for metadata in product_properties]
    async_add_entities(entities)

    # register entity level services
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service("start_p2p_livestream", {}, "_start_p2p_livestream")
    platform.async_register_entity_service("stop_p2p_livestream", {}, "_stop_p2p_livestream")
    platform.async_register_entity_service("start_rtsp_livestream", {}, "_start_rtsp_livestream")
    platform.async_register_entity_service("stop_rtsp_livestream", {}, "_stop_rtsp_livestream")
    platform.async_register_entity_service("ptz_up", {}, "_async_ptz_up")
    platform.async_register_entity_service("ptz_down", {}, "_async_ptz_down")
    platform.async_register_entity_service("ptz_left", {}, "_async_ptz_left")
    platform.async_register_entity_service("ptz_right", {}, "_async_ptz_right")
    platform.async_register_entity_service("ptz_360", {}, "_async_ptz_360")

    platform.async_register_entity_service("trigger_alarm_with_duration", Schema.TRIGGER_ALARM_SERVICE_SCHEMA.value, "_async_alarm_trigger")
    platform.async_register_entity_service("reset_alarm", {}, "_async_reset_alarm")
    platform.async_register_entity_service("quick_response", Schema.QUICK_RESPONSE_SERVICE_SCHEMA.value, "_async_quick_response")


class EufySecurityCamera(Camera, EufySecurityEntity):
    """Base camera entity for integration"""

    def __init__(self, coordinator: EufySecurityDataUpdateCoordinator, metadata: Metadata) -> None:
        Camera.__init__(self)
        EufySecurityEntity.__init__(self, coordinator, metadata)
        self._attr_supported_features = CameraEntityFeature.STREAM
        self._attr_name = f"{self.product.name}"

        # camera image
        self._last_url = None
        self._last_image = None

        # ffmpeg entities
        self.ffmpeg = self.coordinator.hass.data[DATA_FFMPEG]

    async def stream_source(self) -> str:
        _LOGGER.debug(f"stream_source - {self.product.stream_url}")
        return self.product.stream_url

    async def handle_async_mjpeg_stream(self, request):
        stream = CameraMjpeg(self.ffmpeg.binary)
        await stream.open_camera(await self.stream_source())
        try:
            return await async_aiohttp_proxy_stream(self.hass, request, await stream.get_reader(), self.ffmpeg.ffmpeg_stream_content_type)
        finally:
            await stream.close()

    @property
    def available(self) -> bool:
        return True

    async def _start_hass_streaming(self):
        await self._stop_hass_streaming()
        await wait_for_value_to_equal(self.product.__dict__, "stream_status", StreamStatus.STREAMING)
        await self.async_create_stream()
        self.stream.add_provider("hls")
        await self.stream.start()
        await self.async_camera_image()

    async def _stop_hass_streaming(self):
        if self.stream is not None:
            await self.stream.stop()
            self.stream = None

    @property
    def is_streaming(self) -> bool:
        """Return true if the device is recording."""
        # asyncio.ensure_future(self._check_stream_availability())
        return self.product.stream_status == StreamStatus.STREAMING

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        if self.is_streaming is True and self.stream is not None:
            self._last_image = await self.stream.async_get_image(width, height)
            self._last_url = None
        else:
            current_url = get_child_value(self.product.properties, self.metadata.name)
            if current_url != self._last_url and current_url.startswith("https"):
                async with async_get_clientsession(self.coordinator.hass).get(current_url) as response:
                    if response.status == 200:
                        self._last_image = await response.read()
                        self._last_url = current_url
        return self._last_image

    async def _start_p2p_livestream(self) -> None:
        """start byte based livestream on camera"""
        await self.product.start_p2p_livestream(CameraMjpeg(self.ffmpeg.binary))
        await self._start_hass_streaming()

    async def _stop_p2p_livestream(self) -> None:
        """stop byte based livestream on camera"""
        await self._stop_hass_streaming()
        await self.product.stop_p2p_livestream()

    async def _start_rtsp_livestream(self) -> None:
        """start rtsp based livestream on camera"""
        await self.product.start_rtsp_livestream()
        await self._start_hass_streaming()

    async def _stop_rtsp_livestream(self) -> None:
        """stop rtsp based livestream on camera"""
        await self._stop_hass_streaming()
        await self.product.stop_rtsp_livestream()

    async def _async_alarm_trigger(self, duration: int = 10):
        """trigger alarm for a duration on camera"""
        await self.product.trigger_alarm(duration)

    async def _async_reset_alarm(self) -> None:
        """reset ongoing alarm"""
        await self.product.reset_alarm()

    async def async_turn_on(self) -> None:
        """Turn off camera."""
        if self.product.stream_provider == StreamProvider.RTSP:
            await self._start_rtsp_livestream()
        else:
            await self._start_p2p_livestream()

    async def async_turn_off(self) -> None:
        """Turn off camera."""
        if self.product.stream_provider == StreamProvider.RTSP:
            await self._stop_rtsp_livestream()
        else:
            await self._stop_p2p_livestream()

    async def _async_ptz_up(self) -> None:
        await self.product.ptz_up()

    async def _async_ptz_down(self) -> None:
        await self.product.ptz_down()

    async def _async_ptz_left(self) -> None:
        await self.product.ptz_left()

    async def _async_ptz_right(self) -> None:
        await self.product.ptz_right()

    async def _async_ptz_360(self) -> None:
        await self.product.ptz_360()

    async def _async_quick_response(self, voice_id: int) -> None:
        await self.product.quick_response(voice_id)
