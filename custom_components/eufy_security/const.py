import asyncio
from datetime import datetime
from enum import Enum
import logging
from queue import Queue

from homeassistant.config_entries import ConfigEntry

_LOGGER: logging.Logger = logging.getLogger(__package__)

# Base component constants
NAME = "Eufy Security"
DOMAIN = "eufy_security"
VERSION = "0.0.1"
COORDINATOR = "coordinator"
CAPTCHA_CONFIG = "captcha_config"

# Platforms
ALARM_CONTROL_PANEL = "alarm_control_panel"
BINARY_SENSOR = "binary_sensor"
CAMERA = "camera"
SENSOR = "sensor"
LOCK = "lock"
SWITCH = "switch"
SELECT = "select"
PLATFORMS = [CAMERA, BINARY_SENSOR, SENSOR, ALARM_CONTROL_PANEL, LOCK, SWITCH, SELECT]

# Configuration and options
CONF_HOST: str = "host"
CONF_PORT: str = "port"
CONF_CAPTCHA: str = "captcha"
CONF_USE_RTSP_SERVER_ADDON: str = "use_rtsp_server_addon"
CONF_RTSP_SERVER_ADDRESS: str = "rtsp_server_address"
CONF_RTSP_SERVER_PORT: str = "rtsp_server_port"
CONF_FFMPEG_ANALYZE_DURATION: str = "ffmpeg_analyze_duration"
CONF_SYNC_INTERVAL: str = "sync_interval"
CONF_AUTO_START_STREAM: str = "auto_start_stream"
CONF_FIX_BINARY_SENSOR_STATE: str = "fix_binary_sensor_state"
CONF_MAP_EXTRA_ALARM_MODES: str = "map_extra_alarm_modes"
CONF_NAME_FOR_CUSTOM1 = "name_for_custom1"
CONF_NAME_FOR_CUSTOM2 = "name_for_custom2"
CONF_NAME_FOR_CUSTOM3 = "name_for_custom3"

DEFAULT_HOST: str = "0.0.0.0"
DEFAULT_PORT: int = 3000
DEFAULT_USE_RTSP_SERVER_ADDON: bool = False
DEFAULT_RTSP_SERVER_PORT: int = 8554
DEFAULT_SYNC_INTERVAL: int = 600  # seconds
DEFAULT_FFMPEG_ANALYZE_DURATION: float = 1.2  # microseconds
DEFAULT_CODEC: str = "h264"
DEFAULT_AUTO_START_STREAM: bool = True
DEFAULT_FIX_BINARY_SENSOR_STATE: bool = False
DEFAULT_MAP_EXTRA_ALARM_MODES: bool = False
DEFAULT_NAME_FOR_CUSTOM1: str = "Custom 1"
DEFAULT_NAME_FOR_CUSTOM2: str = "Custom 2"
DEFAULT_NAME_FOR_CUSTOM3: str = "Custom 3"


P2P_LIVESTREAMING_STATUS = "p2pLiveStreamingStatus"
RTSP_LIVESTREAMING_STATUS = "rtspLiveStreamingStatus"
STREAMING_EVENT_NAMES = [RTSP_LIVESTREAMING_STATUS, P2P_LIVESTREAMING_STATUS]
LATEST_CODEC = "latest codec"
SET_API_SCHEMA = {
    "messageId": "set_api_schema",
    "command": "set_api_schema",
    "schemaVersion": 7,
}
DRIVER_CONNECT_MESSAGE = {"messageId": "driver_connect", "command": "driver.connect"}
SET_CAPTCHA_MESSAGE = {
    "messageId": "driver_set_captcha",
    "command": "driver.set_captcha",
    "captchaId": None,
    "captcha": None,
}
START_LISTENING_MESSAGE = {"messageId": "start_listening", "command": "start_listening"}
POLL_REFRESH_MESSAGE = {"messageId": "poll_refresh", "command": "driver.poll_refresh"}
GET_P2P_LIVESTREAM_STATUS_PLACEHOLDER = "get_p2p_livestream_status"
GET_RTSP_LIVESTREAM_STATUS_PLACEHOLDER = "get_rtsp_livestream_status"
GET_DEVICE_PROPERTIES_METADATA_MESSAGE = {
    "messageId": "get_device_properties_metadata",
    "command": "device.get_properties_metadata",
    "serialNumber": None,
}
GET_DEVICE_PROPERTIES_MESSAGE = {
    "messageId": "get_device_properties",
    "command": "device.get_properties",
    "serialNumber": None,
}
GET_STATION_PROPERTIES_METADATA_MESSAGE = {
    "messageId": "get_station_properties_metadata",
    "command": "station.get_properties_metadata",
    "serialNumber": None,
}
GET_STATION_PROPERTIES_MESSAGE = {
    "messageId": "get_station_properties",
    "command": "station.get_properties",
    "serialNumber": None,
}
GET_RTSP_LIVESTREAM_STATUS_MESSAGE = {
    "messageId": "get_rtsp_livestream_status",
    "command": "device.is_rtsp_livestreaming",
    "serialNumber": None,
}
GET_P2P_LIVESTREAM_STATUS_MESSAGE = {
    "messageId": "get_p2p_livestream_status",
    "command": "device.is_livestreaming",
    "serialNumber": None,
}
SET_RTSP_STREAM_MESSAGE = {
    "messageId": "set_rtsp_stream_on",
    "command": "device.set_rtsp_stream",
    "serialNumber": None,
    "value": None,
}
SET_RTSP_LIVESTREAM_MESSAGE = {
    "messageId": "start_rtsp_livestream",
    "command": "device.{state}_rtsp_livestream",
    "serialNumber": None,
}
SET_P2P_LIVESTREAM_MESSAGE = {
    "messageId": "start_livesteam",
    "command": "device.{state}_livestream",
    "serialNumber": None,
}
SET_DEVICE_STATE_MESSAGE = {
    "messageId": "enable_device",
    "command": "device.enable_device",
    "serialNumber": None,
    "value": None,
}
SET_GUARD_MODE_MESSAGE = {
    "messageId": "set_guard_mode",
    "command": "station.set_guard_mode",
    "serialNumber": None,
    "mode": None,
}
SET_PROPERTY_MESSAGE = {
    "messageId": "device_set_property",
    "command": "device.set_property",
    "serialNumber": None,
    "name": None,
    "value": None,
}
STATION_TRIGGER_ALARM = {
    "messageId": "trigger_alarm",
    "command": "station.trigger_alarm",
    "serialNumber": None,
    "seconds": 10,
}
STATION_RESET_ALARM = {
    "messageId": "reset_alarm",
    "command": "station.reset_alarm",
    "serialNumber": None,
}
CAMERA_TRIGGER_ALARM = {
    "messageId": "trigger_alarm",
    "command": "device.trigger_alarm",
    "serialNumber": None,
    "seconds": 10,
}
CAMERA_RESET_ALARM = {
    "messageId": "reset_alarm",
    "command": "device.reset_alarm",
    "serialNumber": None,
}
SET_LOCK_MESSAGE = {
    "messageId": "lock_device",
    "command": "device.lock_device",
    "serialNumber": None,
    "value": None,
}


MESSAGE_IDS_TO_PROCESS = [
    START_LISTENING_MESSAGE["messageId"],
    GET_DEVICE_PROPERTIES_MESSAGE["messageId"],
    GET_DEVICE_PROPERTIES_METADATA_MESSAGE["messageId"],
    GET_STATION_PROPERTIES_MESSAGE["messageId"],
    GET_STATION_PROPERTIES_METADATA_MESSAGE["messageId"],
    GET_P2P_LIVESTREAM_STATUS_MESSAGE["messageId"],
    GET_RTSP_LIVESTREAM_STATUS_MESSAGE["messageId"],
    DRIVER_CONNECT_MESSAGE["messageId"],
    SET_CAPTCHA_MESSAGE["messageId"],
]
MESSAGE_TYPES_TO_PROCESS = ["result", "event"]
PROPERTY_CHANGED_PROPERTY_NAME = "event_property_name"
P2P_LIVESTREAM_STARTED = "livestream started"
P2P_LIVESTREAM_STOPPED = "livestream stopped"
RTSP_LIVESTREAM_STARTED = "rtsp livestream started"
RTSP_LIVESTREAM_STOPPED = "rtsp livestream stopped"
EVENT_CONFIGURATION: dict = {
    "connected": {
        "name": "event",
        "value": "event",
        "type": "driver",
    },
    "captcha request": {
        "name": "captcha",
        "value": "captcha",
        "type": "captcha",
    },
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
    P2P_LIVESTREAM_STARTED: {
        "name": P2P_LIVESTREAMING_STATUS,
        "value": "event",
        "type": "state",
    },
    P2P_LIVESTREAM_STOPPED: {
        "name": P2P_LIVESTREAMING_STATUS,
        "value": "event",
        "type": "state",
    },
    RTSP_LIVESTREAM_STARTED: {
        "name": RTSP_LIVESTREAMING_STATUS,
        "value": "event",
        "type": "state",
    },
    RTSP_LIVESTREAM_STOPPED: {
        "name": RTSP_LIVESTREAMING_STATUS,
        "value": "event",
        "type": "state",
    },
    "livestream video data": {
        "name": "video_data",
        "value": "buffer",
        "type": "event",
    },
    "alarm event": {
        "name": "alarmEvent",
        "value": "alarmEvent",
        "type": "state",
    },
}

STATE_ALARM_CUSTOM1 = "custom1"
STATE_ALARM_CUSTOM2 = "custom2"
STATE_ALARM_CUSTOM3 = "custom3"
STATE_GUARD_SCHEDULE = "schedule"
STATE_GUARD_GEO = "geo"
STATE_GUARD_OFF = "off"


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


def get_child_value(data, key, default_value=None):
    value = data
    for x in key.split("."):
        try:
            value = value[x]
        except Exception as ex1:  # pylint: disable=broad-except
            try:
                value = value[int(x)]
            except Exception as ex1:  # pylint: disable=broad-except
                value = default_value
    return value


class Device:
    def __init__(self, serial_number: str, state: dict) -> None:
        self.serial_number: str = serial_number
        self.state: dict = state
        self.name: str = state["name"]
        self.model: str = state["model"]
        self.hardware_version: str = state["hardwareVersion"]
        self.software_version: str = state["softwareVersion"]

        self.properties: dict = None
        self.properties_metadata: dict = None
        self.type_raw: str = None
        self.type: str = None
        self.category: str = None

        self.state[P2P_LIVESTREAMING_STATUS] = False
        self.state[RTSP_LIVESTREAMING_STATUS] = False
        self.is_rtsp_streaming: bool = False
        self.is_p2p_streaming: bool = False
        self.is_streaming: bool = False
        self.stream_source_type: str = ""
        self.stream_source_address: str = ""
        self.codec: str = DEFAULT_CODEC
        self.queue: Queue = Queue()

        self.callback = None

        self.set_global_motion_sensor()

    def set_properties(self, properties: dict):
        self.properties = properties
        self.type_raw = get_child_value(self.properties, "type")
        type = DEVICE_TYPE(self.type_raw)
        self.type = str(type)
        self.category = DEVICE_CATEGORY.get(type, "UNKNOWN")

    def set_properties_metadata(self, properties_metadata: dict):
        self.properties_metadata = properties_metadata

    def is_base_station(self):
        if self.category in ["STATION"]:
            return True
        return False

    def is_camera(self):
        if self.category in ["CAMERA", "DOORBELL"]:
            return True
        return False

    def is_motion_sensor(self):
        if self.category in ["MOTION_SENSOR"]:
            return True
        return False

    def is_lock(self):
        if self.category in ["LOCK"]:
            return True
        return False

    def set_streaming_status(self):
        if self.state[P2P_LIVESTREAMING_STATUS] == P2P_LIVESTREAM_STARTED:
            self.is_p2p_streaming = True
        else:
            self.is_p2p_streaming = False

        if self.state[RTSP_LIVESTREAMING_STATUS] == RTSP_LIVESTREAM_STARTED:
            self.is_rtsp_streaming = True
        else:
            self.is_rtsp_streaming = False

        if self.callback is not None:
            self.callback()

    def set_codec(self, codec: str):
        if codec == "unknown":
            codec = "h264"
        if codec == "h265":
            codec = "hevc"
        self.codec = codec

    def set_streaming_status_callback(self, callback):
        self.callback = callback

    def set_property(self, property_name, value):
        self.state[property_name] = value
        self.set_global_motion_sensor()
        if property_name in STREAMING_EVENT_NAMES:
            self.set_streaming_status()

    def set_global_motion_sensor(self):
        motion_detected = bool(get_child_value(self.state, "motionDetected"))
        person_detected = bool(get_child_value(self.state, "personDetected"))
        pet_detected = bool(get_child_value(self.state, "petDetected"))
        self.state["global_motion_sensor"] = (
            motion_detected or person_detected or pet_detected
        )


class EufyConfig:
    def __init__(self, config_entry: ConfigEntry) -> None:
        self.host: str = config_entry.data.get(CONF_HOST)
        self.port: int = config_entry.data.get(CONF_PORT)
        self.sync_interval: int = config_entry.options.get(
            CONF_SYNC_INTERVAL, DEFAULT_SYNC_INTERVAL
        )
        self.use_rtsp_server_addon: bool = config_entry.options.get(
            CONF_USE_RTSP_SERVER_ADDON, DEFAULT_USE_RTSP_SERVER_ADDON
        )
        self.rtsp_server_address: str = config_entry.options.get(
            CONF_RTSP_SERVER_ADDRESS, self.host
        )
        self.rtsp_server_port: int = config_entry.options.get(
            CONF_RTSP_SERVER_PORT, DEFAULT_RTSP_SERVER_PORT
        )
        self.ffmpeg_analyze_duration: int = config_entry.options.get(
            CONF_FFMPEG_ANALYZE_DURATION, DEFAULT_FFMPEG_ANALYZE_DURATION
        )
        self.auto_start_stream: bool = config_entry.options.get(
            CONF_AUTO_START_STREAM, DEFAULT_AUTO_START_STREAM
        )
        self.fix_binary_sensor_state: bool = config_entry.options.get(
            CONF_FIX_BINARY_SENSOR_STATE, DEFAULT_FIX_BINARY_SENSOR_STATE
        )
        self.map_extra_alarm_modes: bool = config_entry.options.get(
            CONF_MAP_EXTRA_ALARM_MODES, DEFAULT_MAP_EXTRA_ALARM_MODES
        )
        self.name_for_custom1: str = config_entry.options.get(
            CONF_NAME_FOR_CUSTOM1, DEFAULT_NAME_FOR_CUSTOM1
        )
        self.name_for_custom2: str = config_entry.options.get(
            CONF_NAME_FOR_CUSTOM2, DEFAULT_NAME_FOR_CUSTOM2
        )
        self.name_for_custom3: str = config_entry.options.get(
            CONF_NAME_FOR_CUSTOM3, DEFAULT_NAME_FOR_CUSTOM3
        )

        _LOGGER.debug(f"{DOMAIN} - config class initialized")


class CaptchaConfig:
    def __init__(self):
        self.reset()

    def reset(self):
        self.required = False
        self.id = None
        self.image = None
        self.requested_at = None
        self.user_input = None
        self.result = None

    def set(self, id, image):
        self.required = True
        self.id = id
        self.image = image
        self.requested_at = datetime.now()

    def set_input(self, captcha):
        self.user_input = captcha
