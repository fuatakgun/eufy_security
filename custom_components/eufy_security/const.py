from enum import Enum

from homeassistant.const import (
    PERCENTAGE,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_SIGNAL_STRENGTH,
)
from homeassistant.components.binary_sensor import DEVICE_CLASS_MOTION

from .generated import DeviceType


# Base component constants
NAME = "Eufy Security"
DOMAIN = "eufy_security"
VERSION = "0.0.1"

# Platforms
BINARY_SENSOR = "binary_sensor"
CAMERA = "camera"
SENSOR = "sensor"
PLATFORMS = [BINARY_SENSOR, CAMERA, SENSOR]

# Configuration and options
CONF_HOST = "host"
CONF_PORT = "port"

# Update all in every hour
DEFAULT_SYNC_INTERVAL = 600  # seconds

START_LIVESTREAM_AT_INITIALIZE = "start livestream at initialize"

START_LISTENING_MESSAGE = {"messageId": "start_listening", "command": "start_listening"}
POLL_REFRESH_MESSAGE = {"messageId": "poll_refresh", "command": "driver.poll_refresh"}
GET_LIVESTREAM_STATUS_PLACEHOLDER = "get_livestream_status"
GET_PROPERTIES_METADATA_MESSAGE = {
    "messageId": "get_properties_metadata",
    "command": "{0}.get_properties_metadata",
    "serialNumber": None,
}
GET_PROPERTIES_MESSAGE = {
    "messageId": "get_properties",
    "command": "{0}.get_properties",
    "serialNumber": None,
}
GET_LIVESTREAM_STATUS_MESSAGE = {
    "messageId": GET_LIVESTREAM_STATUS_PLACEHOLDER + ".{serial_no}",
    "command": "device.is_livestreaming",
    "serialNumber": None,
}
SET_RTSP_STREAM_MESSAGE = {
    "messageId": "set_rtsp_stream_on",
    "command": "device.set_rtsp_stream",
    "serialNumber": None,
    "value": None,
}
SET_LIVESTREAM_MESSAGE = {
    "messageId": "start_livesteam",
    "command": "device.{state}_livestream",
    "serialNumber": None,
}

MESSAGE_IDS_TO_PROCESS = [
    START_LISTENING_MESSAGE["messageId"],
    GET_PROPERTIES_MESSAGE["messageId"],
    GET_LIVESTREAM_STATUS_MESSAGE["messageId"],
]
MESSAGE_TYPES_TO_PROCESS = ["result", "event"]
PROPERTY_CHANGED_PROPERTY_NAME = "event_property_name"
EVENT_CONFIGURATION: dict = {
    "property changed": {
        "name": PROPERTY_CHANGED_PROPERTY_NAME,
        "value": "value",
        "is_cached": False,
    },
    "person detected": {
        "name": "personDetected",
        "value": "state",
        "is_cached": False,
    },
    "motion detected": {
        "name": "motionDetected",
        "value": "state",
        "is_cached": False,
    },
    "got rtsp url": {
        "name": "rtspUrl",
        "value": "rtspUrl",
        "is_cached": True,
    },
    "livestream started": {
        "name": "liveStreamingStatus",
        "value": "event",
        "is_cached": True,
    },
    "livestream stopped": {
        "name": "liveStreamingStatus",
        "value": "event",
        "is_cached": True,
    },
    "livestream video data": {
        "name": "video_data",
        "value": "buffer",
        "is_cached": True,
        "print_log": False,
    },
    "livestream audio dataX": {
        "name": "audio_data",
        "value": "buffer",
        "is_cached": True,
    },
}

CAMERA_PRESET1_SENSORS = [
    "battery",
    "wifiRSSI",
    "motion_sensor",
    "person_detector_sensor",
]
CAMERA_PRESET1_PROPERTIES = [
    "rtspStream",
    "pictureUrl",
]

CAMERA_PRESET2_SENSORS = ["motion_sensor"]
CAMERA_PRESET2_PROPERTIES = ["pictureUrl"]

DOORBELL_PRESET1_SENSORS = ["motion_sensor", "person_detector_sensor", "ringing_sensor"]
DOORBELL_PRESET1_PROPERTIES = ["pictureUrl"]

DOORBELL_BATTERY_PRESET1_SENSORS = [
    "battery",
    "wifiRSSI",
    "motion_sensor",
    "person_detector_sensor",
    "ringing_sensor",
]

DOORBELL_BATTERY_PRESET1_PROPERTIES = ["pictureUrl"]

# TYPES_TO_SENSORS = {
#     DeviceType.CAMERA_2: CAMERA_PRESET1_SENSORS,
#     DeviceType.CAMERA_2PRO: CAMERA_PRESET1_SENSORS,
#     DeviceType.CAMERA_2C: CAMERA_PRESET1_SENSORS,
#     DeviceType.CAMERA_2CPRO: CAMERA_PRESET1_SENSORS,
#     DeviceType.CAMERA: CAMERA_PRESET2_SENSORS,
#     DeviceType.CAMERA_E: CAMERA_PRESET2_SENSORS,
#     DeviceType.DOORBELL: DOORBELL_PRESET1_SENSORS,
#     DeviceType.BATTERY_DOORBELL: DOORBELL_BATTERY_PRESET1_SENSORS,
#     DeviceType.BATTERY_DOORBELL_2: DOORBELL_BATTERY_PRESET1_SENSORS,
# }
# TYPES_TO_PROPERTIES = {
#     DeviceType.CAMERA_2: CAMERA_PRESET1_PROPERTIES,
#     DeviceType.CAMERA_2PRO: CAMERA_PRESET1_PROPERTIES,
#     DeviceType.CAMERA_2C: CAMERA_PRESET1_PROPERTIES,
#     DeviceType.CAMERA_2CPRO: CAMERA_PRESET1_PROPERTIES,
#     DeviceType.CAMERA: CAMERA_PRESET2_PROPERTIES,
#     DeviceType.CAMERA_E: CAMERA_PRESET2_PROPERTIES,
#     DeviceType.DOORBELL: DOORBELL_PRESET1_PROPERTIES,
#     DeviceType.BATTERY_DOORBELL: DOORBELL_BATTERY_PRESET1_PROPERTIES,
#     DeviceType.BATTERY_DOORBELL_2: DOORBELL_BATTERY_PRESET1_PROPERTIES,
# }


SENSORS = {
    "battery": [
        SENSOR,
        "battery",
        "Battery",
        "battery",
        PERCENTAGE,
        None,
        DEVICE_CLASS_BATTERY,
    ],
    "wifiRSSI": [
        SENSOR,
        "wifiRSSI",
        "Wifi RSSI",
        "wifiRSSI",
        None,
        None,
        DEVICE_CLASS_SIGNAL_STRENGTH,
    ],
    "motion_sensor": [
        BINARY_SENSOR,
        "motion_sensor",
        "Motion Sensor",
        "motionDetected",
        None,
        DEVICE_CLASS_MOTION,
    ],
    "person_detector_sensor": [
        BINARY_SENSOR,
        "person_detector_sensor",
        "Person Detector Sensor",
        "personDetected",
        None,
        DEVICE_CLASS_MOTION,
    ],
    "ringing_sensor": [
        BINARY_SENSOR,
        "ringing_sensor",
        "Ringing Sensor",
        "ringing",
        "mdi:bell-ring",
        None,
    ],
}
