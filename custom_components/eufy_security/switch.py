import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    COORDINATOR,
    DOMAIN,
    LIGHT_PROPERTY,
    Platform,
    PlatformToPropertyType,
)
from .coordinator import EufySecurityDataUpdateCoordinator
from .entity import EufySecurityEntity
from .eufy_security_api.metadata import Metadata
from .eufy_security_api.util import get_child_value
from .util import get_product_properties_by_filter

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Setup switch entities."""

    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN][COORDINATOR]
    product_properties = get_product_properties_by_filter(
        [coordinator.devices.values(), coordinator.stations.values()], PlatformToPropertyType[Platform.SWITCH.name].value
    )
    entities = [
        EufyLightCompatibilitySwitch(coordinator, metadata)
        if metadata.name == LIGHT_PROPERTY
        else EufySwitchEntity(coordinator, metadata)
        for metadata in product_properties
    ]
    async_add_entities(entities)


class EufySwitchEntity(SwitchEntity, EufySecurityEntity):
    """Base switch entity for integration"""

    def __init__(self, coordinator: EufySecurityDataUpdateCoordinator, metadata: Metadata) -> None:
        super().__init__(coordinator, metadata)

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return bool(get_child_value(self.product.properties, self.metadata.name))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.product.set_property(self.metadata, False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self.product.set_property(self.metadata, True)


class EufyLightCompatibilitySwitch(EufySwitchEntity):
    """Compatibility switch retained for existing automations."""

    _attr_entity_registry_visible_default = False

    def __init__(self, coordinator: EufySecurityDataUpdateCoordinator, metadata: Metadata) -> None:
        super().__init__(coordinator, metadata)
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_icon = "mdi:car-light-high"
