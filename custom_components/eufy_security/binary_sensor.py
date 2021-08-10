import logging

from decimal import Decimal

from homeassistant.config_entries import ConfigEntry
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_SOUND,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_POWER,
)

from .const import DOMAIN
from .entity import EufySecurityEntity
from .coordinator import EufySecurityDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass, entry, async_add_devices):
    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN]

    INSTRUMENTS = [
        ("motion_sensor", "Motion Sensor", "motionDetected", None, DEVICE_CLASS_MOTION),
        ("person_detector_sensor", "Person Detector Sensor", "personDetected", None, DEVICE_CLASS_MOTION),
        ("pet_detector_sensor", "Pet Detector Sensor", "petDetected", None, DEVICE_CLASS_MOTION),
        ("sound_detector_sensor", "Sound Detector Sensor", "soundDetected", None, DEVICE_CLASS_SOUND),
        ("crying_detector_sensor", "Crying Detector Sensor", "cryingDetected", None, DEVICE_CLASS_SOUND),
        ("sensor_open", "Sensor Open", "sensorOpen", None, DEVICE_CLASS_DOOR),
        ("ringing_sensor", "Ringing Sensor", "ringing", "mdi:bell-ring", None),
        ("enabled", "Enabled", "enabled", None, DEVICE_CLASS_POWER),
    ]

    entities = []
    for entity in coordinator.state["devices"]:
        for id, description, key, icon, device_class in INSTRUMENTS:
            if not entity.get(key, None) is None:
                entities.append(
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
                )

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

        if self.id == "motion_sensor":
            if entity["category"] in ["MOTION_SENSOR"]:
                self.key = "motionDetection"

        _LOGGER.debug(f"{DOMAIN} - binary init - {self.key}")

    @property
    def is_on(self):
        return self.entity.get(self.key)

    @property
    def state(self):
        return self.entity.get(self.key)

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

    @property
    def state_attributes(self):
        return self.entity
