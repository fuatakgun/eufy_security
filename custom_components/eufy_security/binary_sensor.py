import logging

from decimal import Decimal

from homeassistant.config_entries import ConfigEntry
from homeassistant.components.binary_sensor import DEVICE_CLASS_MOTION

from .const import DOMAIN
from .entity import EufySecurityEntity
from .coordinator import EufySecurityDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass, entry, async_add_devices):
    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN]

    INSTRUMENTS = [
        (
            "motion_sensor",
            "Motion Sensor",
            "motionDetected",
            None,
            DEVICE_CLASS_MOTION,
        ),
        (
            "person_detector_sensor",
            "Person Detector Sensor",
            "personDetected",
            None,
            DEVICE_CLASS_MOTION,
        ),
    ]

    entities = []
    for entity in coordinator.state["devices"]:
        sensors = [
            EufySecurityBinarySensor(
                coordinator,
                entry,
                entity,
                id,
                description,
                key,
                icon,
                device_class,
            )
            for id, description, key, icon, device_class in INSTRUMENTS
        ]
        entities.extend(sensors)

    async_add_devices(entities, True)


class EufySecurityBinarySensor(EufySecurityEntity):
    def __init__(
        self,
        coordinator: EufySecurityDataUpdateCoordinator,
        entry: ConfigEntry,
        entity: dict,
        id: str,
        description: str,
        key: str,
        icon: str,
        device_class: str,
    ):

        super().__init__(coordinator, entry, entity)
        self._id = id
        self.description = description
        self.key = key
        self._icon = icon
        self._device_class = device_class

    @property
    def state(self):
        return self.entity.get(self.key, None)

    @property
    def icon(self):
        return self._icon

    @property
    def device_class(self):
        return self._device_class

    @property
    def name(self):
        return f"{self.entity['name']} {self.description}"

    @property
    def id(self):
        return f"{DOMAIN}_{self.entity.get('serialNumber','missing_serial_number')}_{self._id}_binary_sensor"

    @property
    def unique_id(self):
        return self.id
