import logging
from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import COORDINATOR, DOMAIN, LIGHT_PROPERTY, Platform, PlatformToPropertyType
from .coordinator import EufySecurityDataUpdateCoordinator
from .entity import EufySecurityEntity
from .eufy_security_api.metadata import Metadata
from .eufy_security_api.util import get_child_value
from .util import get_product_properties_by_filter

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up light entities."""

    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN][COORDINATOR]
    product_properties = get_product_properties_by_filter(
        [coordinator.devices.values(), coordinator.stations.values()],
        PlatformToPropertyType[Platform.SWITCH.name].value,
    )
    entities = [
        EufyLightEntity(coordinator, metadata)
        for metadata in product_properties
        if metadata.name == LIGHT_PROPERTY
    ]
    async_add_entities(entities)


class EufyLightEntity(LightEntity, EufySecurityEntity):
    """Eufy controllable light entity."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(self, coordinator: EufySecurityDataUpdateCoordinator, metadata: Metadata) -> None:
        super().__init__(coordinator, metadata)

    @property
    def is_on(self) -> bool:
        """Return whether the light is on."""
        return bool(get_child_value(self.product.properties, self.metadata.name))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.product.set_property(self.metadata, False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        await self.product.set_property(self.metadata, True)
