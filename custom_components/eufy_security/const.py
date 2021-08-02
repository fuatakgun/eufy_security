import logging

import asyncio
from enum import Enum

from homeassistant.const import (
    PERCENTAGE,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_SIGNAL_STRENGTH,
)
from homeassistant.components.binary_sensor import DEVICE_CLASS_MOTION

_LOGGER: logging.Logger = logging.getLogger(__package__)

# Base component constants
NAME = "Eufy Security"
DOMAIN = "eufy_security"
VERSION = "0.0.1"

# Platforms
ALARM_CONTROL_PANEL = "alarm_control_panel"
BINARY_SENSOR = "binary_sensor"
CAMERA = "camera"
SENSOR = "sensor"
PLATFORMS = [BINARY_SENSOR, CAMERA, SENSOR, ALARM_CONTROL_PANEL]

# Configuration and options
CONF_HOST = "host"
CONF_PORT = "port"
CONF_USE_RTSP_SERVER_ADDON = "use_rtsp_server_addon"

# Update all in every hour
DEFAULT_SYNC_INTERVAL = 600  # seconds

START_LIVESTREAM_AT_INITIALIZE = "start livestream at initialize"
SET_API_SCHEMA = {
    "messageId": "set_api_schema",
    "command": "set_api_schema",
    "schemaVersion": 3,
}
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
SET_DEVICE_STATE_MESSAGE = {
    "messageId": "enable_device",
    "command": "device.enable_device",
    "serialNumber": None,
    "value": None
}

SET_GUARD_MODE_MESSAGE = {
    "messageId": "set_guard_mode",
    "command": "station.set_guard_mode",
    "serialNumber": None,
    "mode": None
}

STATION_TRIGGER_ALARM = {
    "messageId": "trigger_alarm",
    "command": "station.trigger_alarm",
    "serialNumber": None,
    "seconds": 10
}

STATION_RESET_ALARM = {
    "messageId": "reset_alarm",
    "command": "station.reset_alarm",
    "serialNumber": None
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
        "type": "state",
    },
    "person detected": {
        "name": "personDetected",
        "value": "state",
        "type": "state",
    },
    "motion detected": {
        "name": "motionDetected",
        "value": "state",
        "type": "state",
    },
    "got rtsp url": {
        "name": "rtspUrl",
        "value": "rtspUrl",
        "type": "cache",
    },
    "livestream started": {
        "name": "liveStreamingStatus",
        "value": "event",
        "type": "cache",
    },
    "livestream stopped": {
        "name": "liveStreamingStatus",
        "value": "event",
        "type": "cache",
    },
    "livestream video data": {
        "name": "video_data",
        "value": "buffer",
        "type": "event",
    },
}

STATE_ALARM_CUSTOM1 = "custom1"
STATE_ALARM_CUSTOM2 = "custom2"
STATE_ALARM_CUSTOM3 = "custom3"
STATE_GUARD_SCHEDULE = "schedule"
STATE_GUARD_GEO = "geo"


class DEVICE_TYPE(Enum):
    STATION = 0
    CAMERA = 1
    SENSOR = 2
    FLOODLIGHT = 3
    CAMERA_E = 4
    DOORBELL = 5
    BATTERY_DOORBELL = 7
    CAMERA2C = 8
    CAMERA2 = 9
    MOTION_SENSOR = 10
    KEYPAD = 11
    CAMERA2_PRO = 14
    CAMERA2C_PRO = 15
    BATTERY_DOORBELL_2 = 16
    INDOOR_CAMERA = 30
    INDOOR_PT_CAMERA = 31
    SOLO_CAMERA = 32
    SOLO_CAMERA_PRO = 33
    INDOOR_CAMERA_1080 = 34
    INDOOR_PT_CAMERA_1080 = 35
    FLOODLIGHT_CAMERA_8422 = 37
    FLOODLIGHT_CAMERA_8423 = 38
    FLOODLIGHT_CAMERA_8424 = 39
    INDOOR_OUTDOOR_CAMERA_1080P_NO_LIGHT = 44
    INDOOR_OUTDOOR_CAMERA_2K = 45
    INDOOR_OUTDOOR_CAMERA_1080P = 46
    LOCK_BASIC = 50
    LOCK_ADVANCED = 51
    LOCK_BASIC_NO_FINGER = 52
    LOCK_ADVANCED_NO_FINGER = 53
    SOLO_CAMERA_SPOTLIGHT_1080 = 60
    SOLO_CAMERA_SPOTLIGHT_2K = 61
    SOLO_CAMERA_SPOTLIGHT_SOLAR = 62


DEVICE_CATEGORY = {
    DEVICE_TYPE.STATION: "STATION",
    DEVICE_TYPE.CAMERA: "CAMERA",
    DEVICE_TYPE.SENSOR: "SENSOR",
    DEVICE_TYPE.FLOODLIGHT: "CAMERA",
    DEVICE_TYPE.CAMERA_E: "CAMERA",
    DEVICE_TYPE.DOORBELL: "DOORBELL",
    DEVICE_TYPE.BATTERY_DOORBELL: "DOORBELL",
    DEVICE_TYPE.CAMERA2C: "CAMERA",
    DEVICE_TYPE.CAMERA2: "CAMERA",
    DEVICE_TYPE.MOTION_SENSOR: "MOTION_SENSOR",
    DEVICE_TYPE.KEYPAD: "KEYPAD",
    DEVICE_TYPE.CAMERA2_PRO: "CAMERA",
    DEVICE_TYPE.CAMERA2C_PRO: "CAMERA",
    DEVICE_TYPE.BATTERY_DOORBELL_2: "DOORBELL",
    DEVICE_TYPE.INDOOR_CAMERA: "CAMERA",
    DEVICE_TYPE.INDOOR_PT_CAMERA: "CAMERA",
    DEVICE_TYPE.SOLO_CAMERA: "CAMERA",
    DEVICE_TYPE.SOLO_CAMERA_PRO: "CAMERA",
    DEVICE_TYPE.INDOOR_CAMERA_1080: "CAMERA",
    DEVICE_TYPE.INDOOR_PT_CAMERA_1080: "CAMERA",
    DEVICE_TYPE.FLOODLIGHT_CAMERA_8422: "CAMERA",
    DEVICE_TYPE.FLOODLIGHT_CAMERA_8423: "CAMERA",
    DEVICE_TYPE.FLOODLIGHT_CAMERA_8424: "CAMERA",
    DEVICE_TYPE.INDOOR_OUTDOOR_CAMERA_1080P_NO_LIGHT: "CAMERA",
    DEVICE_TYPE.INDOOR_OUTDOOR_CAMERA_2K: "CAMERA",
    DEVICE_TYPE.INDOOR_OUTDOOR_CAMERA_1080P: "CAMERA",
    DEVICE_TYPE.LOCK_BASIC: "LOCK",
    DEVICE_TYPE.LOCK_ADVANCED: "LOCK",
    DEVICE_TYPE.LOCK_BASIC_NO_FINGER: "LOCK",
    DEVICE_TYPE.LOCK_ADVANCED_NO_FINGER: "LOCK",
    DEVICE_TYPE.SOLO_CAMERA_SPOTLIGHT_1080: "CAMERA",
    DEVICE_TYPE.SOLO_CAMERA_SPOTLIGHT_2K: "CAMERA",
    DEVICE_TYPE.SOLO_CAMERA_SPOTLIGHT_SOLAR: "CAMERA",
}


async def wait_for_value(
    ref_dict: dict, ref_key: str, value, max_counter: int = 50, interval=0.25
):
    _LOGGER.debug(f"{DOMAIN} - wait start - {ref_key}")
    for counter in range(max_counter):
        _LOGGER.debug(
            f"{DOMAIN} - wait - {counter} - {ref_key} {ref_dict.get(ref_key)}"
        )
        if ref_dict.get(ref_key, value) == value:
            await asyncio.sleep(interval)
        else:
            return True
    return False
