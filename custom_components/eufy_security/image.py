from __future__ import annotations

import asyncio
import contextlib
import logging
import datetime

from base64 import b64decode
from homeassistant.components.image import ImageEntity, ImageEntityDescription

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import COORDINATOR, DOMAIN, Schema
from .coordinator import EufySecurityDataUpdateCoordinator
from .entity import EufySecurityEntity
from .eufy_security_api.metadata import Metadata


_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Setup camera entities."""
    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN][COORDINATOR]
    product_properties = []
    for product in coordinator.devices.values():
        if product.is_camera is True:
            product_properties.append(Metadata.parse(product, {"name": "camera", "label": "Camera"}))

    entities = [EufySecurityImage(coordinator, metadata) for metadata in product_properties]
    async_add_entities(entities)


class EufySecurityImage(ImageEntity, EufySecurityEntity):
    """Base image entity for integration"""

    def __init__(self, coordinator: EufySecurityDataUpdateCoordinator, metadata: Metadata) -> None:
        ImageEntity.__init__(self, coordinator.hass)
        EufySecurityEntity.__init__(self, coordinator, metadata)
        self._attr_name = f"{self.product.name} Event Image"
        self._attr_image_last_updated = None

        # camera image
        self._last_image = None

    async def async_image(self) -> bytes | None:
        """Return bytes of image."""
        if self.product.picture_base64 is not None:
            value = bytearray(self.product.picture_base64["data"]["data"])
            if value != self._last_image:
                self._attr_image_last_updated = datetime.datetime.now(datetime.timezone.utc)
            self._last_image = value
        return self._last_image
