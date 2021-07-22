from enum import Enum

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

START_LISTENING_MESSAGE = {"messageId": "start_listening", "command": "start_listening"}
POLL_REFRESH_MESSAGE = {"messageId": "poll_refresh", "command": "driver.poll_refresh"}
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
    },
    "livestream audio dataX": {
        "name": "audio_data",
        "value": "buffer",
        "is_cached": True,
    },
}
