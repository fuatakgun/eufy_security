import logging

from homeassistant.components.select import SelectEntity
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
    """Setup select entities."""

    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN][COORDINATOR]
    product_properties = get_product_properties_by_filter(
        [coordinator.devices.values(), coordinator.stations.values()], PlatformToPropertyType[Platform.SELECT.name].value
    )
    entities = [EufySelectEntity(coordinator, metadata) for metadata in product_properties]
    async_add_entities(entities)


class EufySelectEntity(SelectEntity, EufySecurityEntity):
    """Base select entity for integration"""

    def __init__(self, coordinator: EufySecurityDataUpdateCoordinator, metadata: Metadata) -> None:
        super().__init__(coordinator, metadata)
        self._attr_options = list(metadata.states.values())

    async def async_select_option(self, option: str):
        to_value = [key for key, value in self.metadata.states.items() if value == option][0]
        await self.product.set_property(self.metadata, str(to_value))

    @property
    def current_option(self) -> str:
        value = str(get_child_value(self.product.properties, self.metadata.name))
        return str(self.metadata.states.get(value, None))
