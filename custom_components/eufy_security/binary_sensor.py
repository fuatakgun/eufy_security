import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_BATTERY_CHARGING,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_SOUND,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from .const import COORDINATOR, DOMAIN, Device, get_child_value
from .coordinator import EufySecurityDataUpdateCoordinator
from .entity import EufySecurityEntity

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_devices
):
    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN][COORDINATOR]

    INSTRUMENTS = [
        (
            "global_motion_sensor",
            "Global Motion Sensor",
            "state.global_motion_sensor",
            None,
            DEVICE_CLASS_MOTION,
            None,
        ),
        (
            "motion_sensor",
            "Motion Sensor",
            "state.motionDetected",
            None,
            DEVICE_CLASS_MOTION,
            None,
        ),
        (
            "person_detector_sensor",
            "Person Detector Sensor",
            "state.personDetected",
            None,
            DEVICE_CLASS_MOTION,
            EntityCategory.DIAGNOSTIC,
        ),
        (
            "person_detection_enabled",
            "Person Detection Enabled",
            "state.personDetection",
            None,
            None,
            EntityCategory.DIAGNOSTIC,
        ),
        (
            "pet_detector_sensor",
            "Pet Detector Sensor",
            "state.petDetected",
            None,
            DEVICE_CLASS_MOTION,
            None,
        ),
        (
            "sound_detector_sensor",
            "Sound Detector Sensor",
            "state.soundDetected",
            None,
            DEVICE_CLASS_SOUND,
            None,
        ),
        (
            "crying_detector_sensor",
            "Crying Detector Sensor",
            "state.cryingDetected",
            None,
            None,
            None,
        ),
        (
            "sensor_open",
            "Sensor Open",
            "state.sensorOpen",
            None,
            DEVICE_CLASS_DOOR,
            None,
        ),
        (
            "battery_low",
            "Battery Low",
            "state.batteryLow",
            None,
            DEVICE_CLASS_BATTERY,
            EntityCategory.DIAGNOSTIC,
        ),
        (
            "ringing_sensor",
            "Ringing Sensor",
            "state.ringing",
            "mdi:bell-ring",
            None,
            None,
        ),
        (
            "notification_person_enabled",
            "Notification for Person",
            "state.notificationPerson",
            "mdi:bell-ring",
            None,
            EntityCategory.DIAGNOSTIC,
        ),
        (
            "notification_pet_enabled",
            "Notification for Pet",
            "state.notificationPet",
            "mdi:bell-ring",
            None,
            EntityCategory.DIAGNOSTIC,
        ),
        (
            "notification_all_other_motion_enabled",
            "Notification for All Other Motion",
            "state.notificationAllOtherMotion",
            "mdi:bell-ring",
            None,
            EntityCategory.DIAGNOSTIC,
        ),
        (
            "notification_crying_enabled",
            "Notification for Crying",
            "state.notificationCrying",
            "mdi:bell-ring",
            None,
            EntityCategory.DIAGNOSTIC,
        ),
        (
            "notification_all_sound_enabled",
            "Notification for All Sound",
            "state.notificationAllSound",
            "mdi:bell-ring",
            None,
            EntityCategory.DIAGNOSTIC,
        ),
        (
            "streaming",
            "Streaming Sensor",
            "is_streaming",
            None,
            DEVICE_CLASS_MOTION,
            EntityCategory.DIAGNOSTIC,
        ),
    ]

    entities = []
    for device in coordinator.devices.values():
        for id, description, key, icon, device_class, entity_category in INSTRUMENTS:
            if not get_child_value(device.__dict__, key) is None:
                entities.append(
                    EufySecurityBinarySensor(
                        coordinator,
                        config_entry,
                        device,
                        id,
                        description,
                        key,
                        icon,
                        device_class,
                        entity_category,
                    )
                )

    async_add_devices(entities, True)


class EufySecurityBinarySensor(EufySecurityEntity):
    def __init__(
        self,
        coordinator: EufySecurityDataUpdateCoordinator,
        config_entry: ConfigEntry,
        device: Device,
        id: str,
        description: str,
        key: str,
        icon: str,
        device_class: str,
        entity_category: str,
    ):
        super().__init__(coordinator, config_entry, device)
        self._id = id
        self.description = description
        self.key = key
        self._icon = icon
        self._device_class = device_class
        self._attr_entity_category = entity_category

        if self.id == "motion_sensor" and device.is_motion_sensor() is True:
            self.key = "motionDetection"

        _LOGGER.debug(
            f"{DOMAIN} - binary init - {self.device.serial_number} {self.key}"
        )

    @property
    def is_on(self):
        value = get_child_value(self.device.__dict__, self.key)
        return bool(value)

    @property
    def state(self):
        if self.coordinator.config.fix_binary_sensor_state is True:
            return STATE_ON if self.is_on else STATE_OFF
        return self.is_on

    @property
    def icon(self):
        return self._icon

    @property
    def device_class(self):
        return self._device_class

    @property
    def name(self):
        return f"{self.device.name} {self.description}"

    @property
    def id(self):
        return f"{DOMAIN}_{self.device.serial_number}_{self._id}_binary_sensor"

    @property
    def unique_id(self):
        return self.id
