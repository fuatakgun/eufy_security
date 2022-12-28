import logging
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import COORDINATOR, DOMAIN
from .coordinator import EufySecurityDataUpdateCoordinator
from .entity import EufySecurityEntity
from .eufy_security_api.metadata import Metadata
from .eufy_security_api.const import MessageField

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Setup lock entities."""
    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN][COORDINATOR]
    properties = []
    for product in coordinator.api.devices.values():
        if product.has(MessageField.LOCKED.value) is True:
            properties.append(product.metadata[MessageField.LOCKED.value])

    entities = [EufySecurityLock(coordinator, metadata) for metadata in properties]
    async_add_entities(entities)


class EufySecurityLock(LockEntity, EufySecurityEntity):
    """Base lock entity for integration"""

    def __init__(self, coordinator: EufySecurityDataUpdateCoordinator, metadata: Metadata) -> None:
        super().__init__(coordinator, metadata)
        self._attr_name = f"{self.product.name}"

    @property
    def is_locked(self):
        return self.product.state.get(self.metadata.name)

    async def async_lock(self, **kwargs: Any) -> None:
        """Initiate lock call"""
        await self.product.set_property(self.metadata, True)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Initiate unlock call"""
        await self.product.set_property(self.metadata, False)
