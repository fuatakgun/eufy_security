import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity


from .const import COORDINATOR, DOMAIN, Platform, PlatformToPropertyType, CameraSensor
from .coordinator import EufySecurityDataUpdateCoordinator
from .entity import EufySecurityEntity
from .eufy_security_api.metadata import Metadata
from .eufy_security_api.util import get_child_value
from .util import get_product_properties_by_filter
from .eufy_security_api.camera import Camera

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Setup sensor entities."""
    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN][COORDINATOR]
    product_properties = get_product_properties_by_filter(
        [coordinator.api.devices.values(), coordinator.api.stations.values()], PlatformToPropertyType[Platform.SENSOR.name].value
    )
    for camera in coordinator.api.devices.values():
        if isinstance(camera, Camera) is True:
            for metadata in CameraSensor:
                product_properties.append(Metadata.parse(camera, {"name": metadata.name, "label": metadata.value}))
    entities = [EufySecuritySensor(coordinator, metadata) for metadata in product_properties]
    async_add_entities(entities)


class EufySecuritySensor(SensorEntity, EufySecurityEntity):
    """Base sensor entity for integration"""

    def __init__(self, coordinator: EufySecurityDataUpdateCoordinator, metadata: Metadata) -> None:
        super().__init__(coordinator, metadata)
        self._attr_state_class = self.description.state_class
        self._attr_native_unit_of_measurement = self.description.unit if self.description.unit else metadata.unit

    @property
    def native_value(self):
        """Return the value reported by the sensor."""
        if self.metadata.name in CameraSensor.__members__:
            if self.metadata.name == "video_queue_size":
                return self.product.video_queue.qsize()
            if self.metadata.name == "stream_provider":
                return self.product.stream_provider.name
            return get_child_value(self.product.__dict__, self.metadata.name)

        value = get_child_value(self.product.properties, self.metadata.name)
        if self.metadata.states is not None:
            try:
                return self.metadata.states[str(value)]
            except KeyError:
                # _LOGGER.info(f"Exception handled - {ValueNotSetException(self.metadata)}")
                pass

        return value
