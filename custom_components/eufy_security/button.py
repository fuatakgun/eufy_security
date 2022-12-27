import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import COORDINATOR, DOMAIN, Platform, PlatformToPropertyType
from .coordinator import EufySecurityDataUpdateCoordinator
from .entity import EufySecurityEntity
from .eufy_security_api.metadata import Metadata
from .eufy_security_api.product import Product
from .eufy_security_api.util import get_child_value
from .util import get_device_info, get_product_properties_by_filter

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Setup binary sensor entities."""
    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN][COORDINATOR]
    product_properties = []
    for product in coordinator.api.devices.values():
        product_properties.append(Metadata.parse(product, {"name": metadata.name, "label": metadata.value}))

    entities = [EufySecurityBinarySensor(coordinator, metadata) for metadata in product_properties]
    async_add_entities(entities)


class EufySecurityBinarySensor(ButtonEntity, EufySecurityEntity):
    """Base button entity for integration"""

    def __init__(self, coordinator: EufySecurityDataUpdateCoordinator, metadata: Metadata) -> None:
        super().__init__(coordinator, metadata)

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return bool(get_child_value(self.product.properties, self.metadata.name))
