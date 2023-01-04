import logging

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    COORDINATOR,
    DOMAIN,
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
        [coordinator.devices.values(), coordinator.stations.values()], PlatformToPropertyType[Platform.NUMBER.name].value
    )
    entities = [EufyNumberEntity(coordinator, metadata) for metadata in product_properties]
    async_add_entities(entities)


class EufyNumberEntity(NumberEntity, EufySecurityEntity):
    """Base switch entity for integration"""

    def __init__(self, coordinator: EufySecurityDataUpdateCoordinator, metadata: Metadata) -> None:
        super().__init__(coordinator, metadata)
        if metadata.min is not None:
            self._attr_native_min_value = metadata.min
        if metadata.max is not None:
            self._attr_native_max_value = metadata.max

    @property
    def native_value(self) -> float:
        """Return number value."""
        value = None
        try:
            value = int(get_child_value(self.product.properties, self.metadata.name))
        except TypeError:
            pass
            # _LOGGER.info(f"Exception handled - {ValueNotSetException(self.metadata)}")
        return value

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self.product.set_property(self.metadata, int(value))
