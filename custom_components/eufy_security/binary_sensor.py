import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
    product_properties = get_product_properties_by_filter(
        [coordinator.devices.values(), coordinator.stations.values()],
        PlatformToPropertyType[Platform.BINARY_SENSOR.name].value,
    )
    entities = [EufySecurityBinarySensor(coordinator, metadata) for metadata in product_properties]

    for device in coordinator.devices.values():
        entities.append(EufySecurityProductEntity(coordinator, device))

    for device in coordinator.stations.values():
        entities.append(EufySecurityProductEntity(coordinator, device))
    async_add_entities(entities)


class EufySecurityBinarySensor(BinarySensorEntity, EufySecurityEntity):
    """Base binary sensor entity for integration"""

    def __init__(self, coordinator: EufySecurityDataUpdateCoordinator, metadata: Metadata) -> None:
        super().__init__(coordinator, metadata)

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return bool(get_child_value(self.product.properties, self.metadata.name))


class EufySecurityProductEntity(BinarySensorEntity, CoordinatorEntity):
    """Debug entity for integration"""

    def __init__(self, coordinator: EufySecurityDataUpdateCoordinator, product: Product) -> None:
        super().__init__(coordinator)
        self.product = product
        self.product.set_state_update_listener(coordinator.async_update_listeners)

        self._attr_unique_id = f"{DOMAIN}_{self.product.product_type.value}_{self.product.serial_no}_debug"
        self._attr_should_poll = False
        self._attr_name = f"{self.product.name} Debug ({self.product.product_type.value})"

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return True

    @property
    def extra_state_attributes(self):
        return {
            "properties": {i: self.product.properties[i] for i in self.product.properties if i != "picture"},
            # "metadata": self.product.metadata_org,
            "commands": self.product.commands,
            "voices": self.product.voices if self.product.is_camera else None,
        }

    @property
    def device_info(self):
        return get_device_info(self.product)
