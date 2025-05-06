"""Constants for integration"""
from enum import Enum, auto
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import Platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import make_entity_service_schema
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
DISCONNECTED = "eufy-security-ws-disconnected"

PLATFORMS: list[str] = [
    Platform.BINARY_SENSOR,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.LOCK,
    Platform.ALARM_CONTROL_PANEL,
    Platform.NUMBER,
    Platform.CAMERA,
    Platform.BUTTON,
    Platform.IMAGE,
]


class Schema(Enum):
    """General used service schema definition"""

    PTZ_SERVICE_SCHEMA = make_entity_service_schema({vol.Required("direction"): cv.string})
    PRESET_POSITION_SERVICE_SCHEMA = make_entity_service_schema({vol.Required("position"): cv.Number})
    TRIGGER_ALARM_SERVICE_SCHEMA = make_entity_service_schema({vol.Required("duration"): cv.Number})
    QUICK_RESPONSE_SERVICE_SCHEMA = make_entity_service_schema({vol.Required("voice_id"): cv.Number})
    CHIME_SERVICE_SCHEMA = make_entity_service_schema({vol.Required("ringtone"): cv.Number})
    SNOOZE = make_entity_service_schema(
        {
            vol.Required("snooze_time"): cv.Number,
            vol.Required("snooze_chime"): cv.boolean,
            vol.Required("snooze_motion"): cv.boolean,
            vol.Required("snooze_homebase"): cv.boolean,
        }
    )


class PropertyToEntityDescription(Enum):
    """Device Property specific entity description"""

    # device camera
    pictureUrl = EntityDescription(id=auto())
    camera = EntityDescription(id=auto())

    # device sensor
    battery = EntityDescription(id=auto(), state_class=SensorStateClass.MEASUREMENT, device_class=SensorDeviceClass.BATTERY, category=EntityCategory.DIAGNOSTIC)
    batteryTemperature = EntityDescription(id=auto(), device_class=SensorDeviceClass.TEMPERATURE, category=EntityCategory.DIAGNOSTIC)
    lastChargingDays = EntityDescription(id=auto(), unit="d", category=EntityCategory.DIAGNOSTIC)
    wifiRssi = EntityDescription(id=auto(), device_class=SensorDeviceClass.SIGNAL_STRENGTH, category=EntityCategory.DIAGNOSTIC)
    wifiSignalLevel = EntityDescription(id=auto(), icon="mdi:signal", category=EntityCategory.DIAGNOSTIC)
    personName = EntityDescription(id=auto(), icon="mdi:account-question")
    rtspStreamUrl = EntityDescription(id=auto(), icon="mdi:movie", category=EntityCategory.DIAGNOSTIC)
    chargingStatus = EntityDescription(id=auto(), icon="mdi:ev-station", category=EntityCategory.DIAGNOSTIC)
    snoozeStartTime = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    snooze = EntityDescription(id=auto(), icon="mdi:alarm-snooze")
    snoozeTime = EntityDescription(id=auto(), icon="mdi:alarm-snooze")
    doorSensor1BatteryLevel = EntityDescription(id=auto(), state_class=SensorStateClass.MEASUREMENT, category=EntityCategory.DIAGNOSTIC)
    doorSensor2BatteryLevel = EntityDescription(id=auto(), state_class=SensorStateClass.MEASUREMENT, category=EntityCategory.DIAGNOSTIC)


    stream_provider = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    stream_url = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    stream_status = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    video_queue_size = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    audio_queue_size = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)


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
    identityPersonDetected = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    strangerPersonDetected = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    vehicleDetected = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    dogDetected = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    dogLickDetected = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    dogPoopDetected = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    radarMotionDetected = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    someoneLoitering = EntityDescription(id=auto())
    packageTaken = EntityDescription(id=auto())
    packageStranded = EntityDescription(id=auto())
    packageDelivered = EntityDescription(id=auto())
    soundDetectionRoundLook = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    deliveryGuard = EntityDescription(id=auto(), category=EntityCategory.CONFIG)
    deliveryGuardPackageGuarding = EntityDescription(id=auto(), category=EntityCategory.CONFIG)
    snoozeHomebase = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    snoozeMotion = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    snoozeChime = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    doorSensor1LowBattery = EntityDescription(id=auto(), device_class=BinarySensorDeviceClass.BATTERY, category=EntityCategory.DIAGNOSTIC)
    doorSensor2LowBattery = EntityDescription(id=auto(), device_class=BinarySensorDeviceClass.BATTERY, category=EntityCategory.DIAGNOSTIC)
    connected = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)

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
    lightSettingsEnable = EntityDescription(id=auto(), category=EntityCategory.CONFIG)

    microphone = EntityDescription(id=auto(), icon="mdi:microphone", category=EntityCategory.CONFIG)
    speaker = EntityDescription(id=auto(), icon="mdi:volume-high", category=EntityCategory.CONFIG)
    audioRecording = EntityDescription(id=auto(), icon="mdi:record-circle", category=EntityCategory.CONFIG)
    loiteringDetection = EntityDescription(id=auto(), category=EntityCategory.CONFIG)
    motionDetectionTypePet = EntityDescription(id=auto(), category=EntityCategory.CONFIG)
    motionDetectionTypeVehicle = EntityDescription(id=auto(), category=EntityCategory.CONFIG)
    motionDetectionTypeHuman = EntityDescription(id=auto(), category=EntityCategory.CONFIG)
    motionDetectionTypeHumanRecognition = EntityDescription(id=auto(), category=EntityCategory.CONFIG)
    motionDetectionTypeAllOtherMotions = EntityDescription(id=auto(), category=EntityCategory.CONFIG)
    door1Open = EntityDescription(id=auto())
    door2Open = EntityDescription(id=auto())

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
    lightSettingsManualLightingActiveMode = EntityDescription(id=auto(), icon="mdi:cog-play", category=EntityCategory.CONFIG)
    lightSettingsBrightnessManual = EntityDescription(id=auto(), icon="mdi:brightness-percent", category=EntityCategory.CONFIG)
    lightSettingsManualDailyLighting = EntityDescription(id=auto(), category=EntityCategory.CONFIG)
    lightSettingsScheduleDynamicLighting = EntityDescription(id=auto(), category=EntityCategory.CONFIG)

    # station sensor
    currentMode = EntityDescription(id=auto(), icon="mdi:security")
    guardMode = EntityDescription(id=auto(), icon="mdi:security")

    # station select
    promptVolume = EntityDescription(id=auto(), icon="mdi:volume-medium", category=EntityCategory.CONFIG)
    alarmVolume = EntityDescription(id=auto(), icon="mdi:volume-medium", category=EntityCategory.CONFIG)

    # station number
    alarm = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    alarmArmDelay = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    alarmDelay = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)

    # lock sensor
    wrongTryProtectAlert = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    jammedAlert = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    shakeAlert = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    lockStatus = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)
    leftOpenAlarm = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)

    # fallback
    default = EntityDescription(id=auto(), category=EntityCategory.DIAGNOSTIC)


class PlatformToPropertyType(Enum):
    """Platform specific filters to select properties"""

    SENSOR = MetadataFilter(readable=True, writeable=False, types=[PropertyType.number, PropertyType.string])
    BINARY_SENSOR = MetadataFilter(readable=True, writeable=False, types=[PropertyType.boolean])
    SWITCH = MetadataFilter(readable=True, writeable=True, types=[PropertyType.boolean])
    SELECT = MetadataFilter(readable=True, writeable=True, types=[PropertyType.number], any_fields=[MessageField.STATES.value])
    NUMBER = MetadataFilter(readable=True, writeable=True, types=[PropertyType.number], no_fields=[MessageField.STATES.value])
    DEVICE_TRACKER = MetadataFilter(readable=True, writeable=False, types=[PropertyType.boolean])