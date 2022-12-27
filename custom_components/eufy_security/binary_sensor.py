import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    """Setup binary sensor entities."""
    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN][COORDINATOR]
    product_properties = get_product_properties_by_filter(
        [coordinator.api.devices.values(), coordinator.api.stations.values()], PlatformToPropertyType[Platform.BINARY_SENSOR.name].value
    )
    entities = [EufySecurityBinarySensor(coordinator, metadata) for metadata in product_properties]
    async_add_entities(entities)


class EufySecurityBinarySensor(BinarySensorEntity, EufySecurityEntity):
    """Base binary sensor entity for integration"""

    def __init__(self, coordinator: EufySecurityDataUpdateCoordinator, metadata: Metadata) -> None:
        super().__init__(coordinator, metadata)

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return bool(get_child_value(self.product.properties, self.metadata.name))
