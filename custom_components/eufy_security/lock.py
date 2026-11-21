import logging
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import ATTR_CODE

from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.exceptions import HomeAssistantError

from .const import COORDINATOR, DOMAIN
from .coordinator import EufySecurityDataUpdateCoordinator
from .entity import EufySecurityEntity
from .eufy_security_api.const import MessageField
from .eufy_security_api.metadata import Metadata
from .eufy_security_api.util import get_child_value

_LOGGER: logging.Logger = logging.getLogger(__package__)

# eufy-security-client only accepts smart safe PINs of 4 to 8 digits, each 1 to 6
SAFE_PIN_FORMAT = r"^[1-6]{4,8}$"


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Setup lock entities."""
    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN][COORDINATOR]
    properties = []
    for product in coordinator.devices.values():
        if product.has(MessageField.LOCKED.value) is True:
            properties.append(product.metadata[MessageField.LOCKED.value])

    entities = [EufySecurityLock(coordinator, metadata) for metadata in properties]
    async_add_entities(entities)


class EufySecurityLock(LockEntity, EufySecurityEntity):
    """Base lock entity for integration"""

    def __init__(self, coordinator: EufySecurityDataUpdateCoordinator, metadata: Metadata) -> None:
        super().__init__(coordinator, metadata)
        self._attr_name = f"{self.product.name}"
        if self.product.is_safe_lock is True:
            # a safe only opens after its PIN is checked, so have Home Assistant ask for one
            self._attr_code_format = SAFE_PIN_FORMAT

    @property
    def is_locked(self):
        return get_child_value(self.product.properties, self.metadata.name)

    async def async_lock(self, **kwargs: Any) -> None:
        """Initiate lock call"""
        if self.product.is_safe_lock is True:
            raise HomeAssistantError(f"Locking is not supported for lock ({self.product.name})")
        await self.product.set_property(self.metadata, True)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Initiate unlock call"""
        code = kwargs.get(ATTR_CODE, None)
        if self.product.is_safe_lock is True:
            # a safe's locked property is read-only; it opens only through PIN check + unlock
            if not code:
                raise HomeAssistantError(f"A PIN is required to unlock ({self.product.name})")
            try:
                verified = await self.product.unlock(code)
            except TimeoutError as exc:
                raise HomeAssistantError(f"No answer to the PIN check from ({self.product.name}); it may be out of reach") from exc
            if verified is False:
                raise HomeAssistantError(f"PIN verification failed for lock ({self.product.name})")
        else:
            await self.product.set_property(self.metadata, False)
