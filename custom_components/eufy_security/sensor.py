from enum import Enum
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import COORDINATOR, DOMAIN, Platform, PlatformToPropertyType
from .coordinator import EufySecurityDataUpdateCoordinator
from .entity import EufySecurityEntity
from .eufy_security_api.metadata import Metadata
from .eufy_security_api.util import get_child_value
from .util import get_product_properties_by_filter

PERSON_NAME = "personName"
EMPTY = ""
UNKNOWN = "Unknown"
PERSON_NAME_STATE_EMPTY = "No Person"
PERSON_NAME_STATE_UNKNOWN = "Unknown Person"
PERSON_NAME_VALUE_TO_STATE = {
    EMPTY: PERSON_NAME_STATE_EMPTY,
    UNKNOWN: PERSON_NAME_STATE_UNKNOWN,
}

_LOGGER: logging.Logger = logging.getLogger(__package__)


class CameraSensor(Enum):
    """Camera specific class attributes to be presented as sensor"""

    stream_provider = "Stream Provider"
    stream_url = "Stream URL"
    stream_status = "Stream Status"
    video_queue_size = "Video Queue Size"
    audio_queue_size = "Audio Queue Size"



async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Setup sensor entities."""
    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN][COORDINATOR]
    product_properties = get_product_properties_by_filter(
        [coordinator.devices.values(), coordinator.stations.values()], PlatformToPropertyType[Platform.SENSOR.name].value
    )
    for camera in coordinator.devices.values():
        if camera.is_camera is True:
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
            if self.metadata.name == CameraSensor.video_queue_size.name:
                return len(self.product.video_queue)
            if self.metadata.name == CameraSensor.audio_queue_size.name:
                return len(self.product.audio_queue)
            if self.metadata.name == CameraSensor.stream_provider.name:
                return self.product.stream_provider.name
            return get_child_value(self.product.__dict__, self.metadata.name)

        value = get_child_value(self.product.properties, self.metadata.name)

        if self.metadata.name == PERSON_NAME:
            return PERSON_NAME_VALUE_TO_STATE.get(value, value)

        if self.metadata.states is not None:
            try:
                return self.metadata.states[str(value)]
            except KeyError:
                # _LOGGER.info(f"Exception handled - {ValueNotSetException(self.metadata)}")
                pass
        if len(str(value)) > 250:
            value = str(value)[-250:]
        return value
