"""Constants for integration"""
from enum import Enum, auto
import logging

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
    Platform,
)
from homeassistant.helpers.entity import EntityCategory

from .eufy_security_api.const import MessageField, PropertyType
from .eufy_security_api.metadata_filter import MetadataFilter
from .model import EntityDescription

_LOGGER: logging.Logger = logging.getLogger(__package__)

# Base component constants
NAME = "Eufy Security"
DOMAIN = "eufy_security"
VERSION = "1.0.0"
COORDINATOR = "coordinator"
CAPTCHA_CONFIG = "captcha_config"


PLATFORMS: list[str] = [
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.LOCK,
    Platform.ALARM_CONTROL_PANEL,
    Platform.NUMBER,
    Platform.CAMERA,
    # Platform.BUTTON,
]


class CameraSensor(Enum):
    """Camera specific class attributes to be presented as sensor"""

    stream_provider = "Stream Provider"
    stream_url = "Stream URL"
    stream_status = "Stream Status"
    codec = "Video Codec"
    video_queue_size = "Video Queue Size"


class PropertyToEntityDescription(Enum):
    """Device Property specific entity description"""

    # device camera
    pictureUrl = EntityDescription(id=auto())
    camera = EntityDescription(id=auto())

    # device sensor
    battery = EntityDescription(
        id=auto(), state_class=SensorStateClass.MEASUREMENT, device_class=SensorDeviceClass.BATTERY, category=EntityCategory.DIAGNOSTIC
    )
    batteryTemperature = EntityDescription(id=auto(), device_class=SensorDeviceClass.TEMPERATURE, category=EntityCategory.DIAGNOSTIC)
    lastChargingDays = EntityDescription(id=auto(), unit="d", category=EntityCategory.DIAGNOSTIC)
    wifiRssi = EntityDescription(id=auto(), device_class=SensorDeviceClass.SIGNAL_STRENGTH, category=EntityCategory.DIAGNOSTIC)
    wifiSignalLevel = EntityDescription(id=auto(), icon="mdi:signal", category=EntityCategory.DIAGNOSTIC)
    personName = EntityDescription(id=auto(), icon="mdi:account-question")
    rtspStreamUrl = EntityDescription(id=auto(), icon="mdi:movie", category=EntityCategory.DIAGNOSTIC)
    chargingStatus = EntityDescription(id=auto(), icon="mdi:ev-station", category=EntityCategory.DIAGNOSTIC)
    stream_provider = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    stream_url = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    stream_status = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    codec = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    video_queue_size = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)

    # device binary sensor
    motionDetected = EntityDescription(id=auto(), device_class=BinarySensorDeviceClass.MOTION)
    personDetected = EntityDescription(id=auto(), device_class=BinarySensorDeviceClass.MOTION)
    petDetected = EntityDescription(id=auto(), device_class=BinarySensorDeviceClass.MOTION)
    soundDetected = EntityDescription(id=auto(), device_class=BinarySensorDeviceClass.SOUND)
    cryingDetected = EntityDescription(id=auto(), icon="mdi:emoticon-cry", device_class=BinarySensorDeviceClass.SOUND)
    sensorOpen = EntityDescription(id=auto(), device_class=BinarySensorDeviceClass.DOOR)
    batteryLow = EntityDescription(id=auto(), device_class=BinarySensorDeviceClass.BATTERY)
    ringing = EntityDescription(id=auto(), icon="mdi:bell-ring", device_class=BinarySensorDeviceClass.RUNNING)
    notificationPerson = EntityDescription(id=auto(), icon="mdi:message-badge", category=EntityCategory.CONFIG)
    notificationPet = EntityDescription(id=auto(), icon="mdi:message-badge", category=EntityCategory.CONFIG)
    notificationAllOtherMotion = EntityDescription(id=auto(), icon="mdi:message-badge", category=EntityCategory.CONFIG)
    notificationCrying = EntityDescription(id=auto(), icon="mdi:message-badge", category=EntityCategory.CONFIG)
    notificationAllSound = EntityDescription(id=auto(), icon="mdi:message-badge", category=EntityCategory.CONFIG)

    # device switch
    enabled = EntityDescription(id=auto())
    antitheftDetection = EntityDescription(id=auto(), icon="mdi:key", category=EntityCategory.CONFIG)
    autoNightvision = EntityDescription(id=auto(), icon="mdi:lightbulb-night", category=EntityCategory.CONFIG)
    statusLed = EntityDescription(id=auto(), icon="mdi:alarm-light-outline", category=EntityCategory.CONFIG)
    motionDetection = EntityDescription(id=auto(), category=EntityCategory.CONFIG)
    personDetection = EntityDescription(id=auto(), category=EntityCategory.CONFIG)
    petDetection = EntityDescription(id=auto(), category=EntityCategory.CONFIG)
    cryingDetection = EntityDescription(id=auto(), icon="mdi:emoticon-cry", category=EntityCategory.CONFIG)
    chimeIndoor = EntityDescription(id=auto(), icon="mdi:bell-ring", category=EntityCategory.CONFIG)
    motionTracking = EntityDescription(id=auto(), icon="mdi:radar", category=EntityCategory.CONFIG)
    rtspStream = EntityDescription(id=auto(), icon="mdi:movie", category=EntityCategory.CONFIG)
    light = EntityDescription(id=auto(), icon="mdi:car-light-high", category=EntityCategory.CONFIG)
    microphone = EntityDescription(id=auto(), icon="mdi:microphone", category=EntityCategory.CONFIG)
    speaker = EntityDescription(id=auto(), icon="mdi:volume-high", category=EntityCategory.CONFIG)
    audioRecording = EntityDescription(id=auto(), icon="mdi:record-circle", category=EntityCategory.CONFIG)

    # device select
    powerSource = EntityDescription(id=auto(), icon="mdi:power-plug", category=EntityCategory.DIAGNOSTIC)
    powerWorkingMode = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    videoStreamingQuality = EntityDescription(id=auto(), category=EntityCategory.CONFIG)
    videoRecordingQuality = EntityDescription(id=auto(), category=EntityCategory.CONFIG)
    rotationSpeed = EntityDescription(id=auto(), category=EntityCategory.CONFIG)
    chimeHomebaseRingtoneVolume = EntityDescription(id=auto(), category=EntityCategory.CONFIG)
    motionDetectionType = EntityDescription(id=auto(), category=EntityCategory.CONFIG)
    motionDetectionSensitivity = EntityDescription(id=auto(), category=EntityCategory.CONFIG)
    speakerVolume = EntityDescription(id=auto(), category=EntityCategory.CONFIG)
    nightvision = EntityDescription(id=auto(), icon="mdi:shield-moon", category=EntityCategory.CONFIG)

    # station sensor
    currentMode = EntityDescription(id=auto(), icon="mdi:security", category=EntityCategory.DIAGNOSTIC)
    guardMode = EntityDescription(id=auto(), icon="mdi:security", category=EntityCategory.DIAGNOSTIC)

    # station select
    promptVolume = EntityDescription(id=auto(), icon="mdi:volume-medium", category=EntityCategory.CONFIG)
    alarmVolume = EntityDescription(id=auto(), icon="mdi:volume-medium", category=EntityCategory.CONFIG)

    # station number
    alarm = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    alarmArmDelay = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    alarmDelay = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)


class PlatformToPropertyType(Enum):
    """Platform specific filters to select properties"""

    SENSOR = MetadataFilter(readable=True, writeable=False, types=[PropertyType.number, PropertyType.string])
    BINARY_SENSOR = MetadataFilter(readable=True, writeable=False, types=[PropertyType.boolean])
    SWITCH = MetadataFilter(readable=True, writeable=True, types=[PropertyType.boolean])
    SELECT = MetadataFilter(readable=True, writeable=True, types=[PropertyType.number], any_fields=[MessageField.STATES.value])
    NUMBER = MetadataFilter(readable=True, writeable=True, types=[PropertyType.number], no_fields=[MessageField.STATES.value])


class CurrentModeToState(Enum):
    """Alarm Entity Mode to State"""

    NONE = -1
    AWAY = 0
    HOME = 1
    CUSTOM_BYPASS = 3
    NIGHT = 4
    VACATION = 5
    DISARMED = 63


class CurrentModeToStateValue(Enum):
    """Alarm Entity Mode to State Value"""

    NONE = "Unknown"
    AWAY = STATE_ALARM_ARMED_AWAY
    HOME = STATE_ALARM_ARMED_HOME
    CUSTOM_BYPASS = auto()
    NIGHT = auto()
    VACATION = auto()
    DISARMED = STATE_ALARM_DISARMED
    TRIGGERED = STATE_ALARM_TRIGGERED
    ALARM_DELAYED = "Alarm delayed"
