import logging

from decimal import Decimal

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_SOUND,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_POWER,
)

from .const import DOMAIN, Device
from .const import get_child_value
from .entity import EufySecurityEntity
from .coordinator import EufySecurityDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_devices):
    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN]

    INSTRUMENTS = [
        ("status_led_enabled", "Status Led Enabled", "state.statusLed", "mdi: led-on", None),
        
        ("motion_sensor", "Motion Sensor", "state.motionDetected", None, DEVICE_CLASS_MOTION),
        ("motion_detection_enabled", "Motion Detection Enabled", "state.motionDetection", None, DEVICE_CLASS_MOTION),
        ("person_detector_sensor", "Person Detector Sensor", "state.personDetected", None, DEVICE_CLASS_MOTION),
        ("person_detection_enabled", "Person Detection Enabled", "state.personDetection", None, DEVICE_CLASS_MOTION),
        ("pet_detector_sensor", "Pet Detector Sensor", "state.petDetected", None, DEVICE_CLASS_MOTION),
        ("pet_detection_enabled", "Pet Detection Enabled", "state.petDetection", "mdi: dog", None),
        ("sound_detector_sensor", "Sound Detector Sensor", "state.soundDetected", None, DEVICE_CLASS_SOUND),
        ("sound_detection_enabled", "Sound Detection Enabled", "state.soundDetection", "mdi: account-voice", None),
        ("crying_detector_sensor", "Crying Detector Sensor", "state.cryingDetected", None, DEVICE_CLASS_SOUND),

        ("sensor_open", "Sensor Open", "state.sensorOpen", None, DEVICE_CLASS_DOOR),

        ("ringing_sensor", "Ringing Sensor", "state.ringing", "mdi:bell-ring", None),

        ("motion_tracking_enabled", "Motion Tracking", "state.motionTracking", "mdi:go-kart-track", None),

        ("notification_person_enabled", "Notification for Person", "state.notificationPerson", "mdi:bell-ring", None),
        ("notification_pet_enabled", "Notification for Pet", "state.notificationPet", "mdi:bell-ring", None),
        ("notification_all_other_motion_enabled", "Notification for All Other Motion", "state.notificationAllOtherMotion", "mdi:bell-ring", None),
        ("notification_crying_enabled", "Notification for Crying", "state.notificationCrying", "mdi:bell-ring", None),
        ("notification_all_sound_enabled", "Notification for All Sound", "state.notificationAllSound", "mdi:bell-ring", None),

        ("speaker_enabled", "Speaker", "state.speaker", "mdi:bullhorn", None),
        ("microphone_enabled", "Microphone", "state.microphone", "mdi:microphone", None),
        ("auto_night_vision_enabled", "Auto Night vision", "state.autoNightvision", "mdi:weather-night", None),
        ("audio_recording_enabled", "Audio Recording", "state.audioRecording", "mdi:record-rec", None),

        ("enabled", "Enabled", "state.enabled", None, DEVICE_CLASS_POWER),
        ("streaming", "Streaming Sensor", "is_streaming", None, DEVICE_CLASS_MOTION),
        ("rtsp_stream_enabled", "RTSP Stream", "state.rtspStream", "mdi:cast-connected", None),
    ]

    entities = []
    for device in coordinator.devices.values():
        for id, description, key, icon, device_class in INSTRUMENTS:
            if not get_child_value(device.__dict__, key) is None:
                entities.append(EufySecurityBinarySensor(coordinator, config_entry, device, id, description, key, icon, device_class))

    async_add_devices(entities, True)


class EufySecurityBinarySensor(EufySecurityEntity):
    def __init__(
        self, coordinator: EufySecurityDataUpdateCoordinator, config_entry: ConfigEntry, device: Device, id: str, description: str, key: str, icon: str, device_class: str):
        super().__init__(coordinator, config_entry, device)
        self._id = id
        self.description = description
        self.key = key
        self._icon = icon
        self._device_class = device_class

        if self.id == "motion_sensor" and device.is_motion_sensor() == True:
            self.key = "motionDetection"

        _LOGGER.debug(f"{DOMAIN} - binary init - {self.key}")

    @property
    def is_on(self):
        return get_child_value(self.device.__dict__, self.key)

    @property
    def state(self):
        return get_child_value(self.device.__dict__, self.key)

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