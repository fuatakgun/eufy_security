"""Define all constants for module."""
from enum import Enum
import logging

from .command_description import CommandDescription

_LOGGER: logging.Logger = logging.getLogger(__package__)

SCHEMA_VERSION = 21

UNSUPPORTED = "Unsupported"

STREAM_TIMEOUT_SECONDS = 15
STREAM_SLEEP_SECONDS = 0.25
GO2RTC_RTSP_PORT = 8554
GO2RTC_API_PORT = 1984
GO2RTC_API_URL = "http://{0}:{1}/api/stream"


class MessageField(Enum):
    """Incoming or outgoing message field types"""

    # general fields
    DUMMY = "dummy"
    MESSAGE_ID = "messageId"
    ERROR_CODE = "errorCode"
    DOMAIN = "domain"
    COMMAND = "command"
    TYPE = "type"
    SUCCESS = "success"
    STATE = "state"
    CONNECTED = "connected"
    SOURCE = "source"
    SCHEMA_VERSION = "schemaVersion"
    LOG_LEVEL = "level"
    RUNTIME = "runtime"
    SERIAL_NO = "serialNumber"
    PROPERTIES = "properties"
    COMMANDS = "commands"
    NAME = "name"
    VALUE = "value"
    MODEL = "model"
    HARDWARE_VERSION = "hardwareVersion"
    SOFTWARE_VERSION = "softwareVersion"
    LABEL = "label"
    READABLE = "readable"
    WRITEABLE = "writeable"
    UNIT = "unit"
    MIN = "min"
    MAX = "max"
    STATES = "states"

    # captcha
    CAPTCHA_ID = "captchaId"
    CAPTCHA_IMG = "captcha"

    # mfa
    VERIFY_CODE = "verifyCode"

    # streaming specific
    RTSP_STREAM = "rtspStream"
    RTSP_STREAM_URL = "rtspStreamUrl"

    # lock specific
    LOCKED = "locked"
    PIN = "pin"
    SUCCESSFULL = "successfull"

    # alarm control panel specific
    CURRENT_MODE = "currentMode"
    GUARD_MODE = "guardMode"
    SECONDS = "seconds"
    RINGTONE = "ringtone"

    # camera specific
    PICTURE_URL = "pictureUrl"
    PICTURE = "picture"
    DIRECTION = "direction"
    POSITION = "position"
    LIVE_STREAMING = "livestreaming"
    VOICES = "voices"
    VOICE_ID = "voiceId"

    # snooze
    SNOOZE_TIME = "snoozeTime"
    SNOOZE_CHIME = "snoozeChime"
    SNOOZE_MOTION = "snoozeMotion"
    SNOOZE_HOMEBASE = "snoozeHomebase"

    # get events
    MAX_RESULTS = "maxResults"
    DEVICE_SERIAL_NO = "deviceSN"


# https://bropat.github.io/eufy-security-ws/#/api_events?id=device-level-events
class EventNameToHandler(Enum):
    """Handler names to incoming event types"""

    verify_code = "verify code"
    captcha_request = "captcha request"
    property_changed = "property changed"
    got_rtsp_url = "got rtsp url"
    livestream_started = "livestream started"
    livestream_stopped = "livestream stopped"
    rtsp_livestream_started = "rtsp livestream started"
    rtsp_livestream_stopped = "rtsp livestream stopped"
    livestream_video_data_received = "livestream video data"
    livestream_audio_data_received = "livestream audio data"
    pin_verified = "pin verified"
    connected = "connected"
    disconnected = "disconnected"
    connection_error = "connection error"


class ProductType(Enum):
    """Product type"""

    station = "station"
    device = "device"


class PropertyType(Enum):
    """Property type"""

    number = "number"
    string = "string"
    boolean = "boolean"
    object = "object"


class ProductCommand(Enum):
    """Important Product Commands - Product function to description+remote command"""

    start_livestream = CommandDescription("Start P2P Stream", "start_livestream")
    stop_livestream = CommandDescription("Stop P2P Stream", "stop_livestream")
    start_rtsp_livestream = CommandDescription("Start RTSP Stream", "is_rtsp_enabled")
    stop_rtsp_livestream = CommandDescription("Stop RTSP Stream", "is_rtsp_enabled")
    ptz_up = CommandDescription("PTZ Up", "pan_and_tilt")
    ptz_down = CommandDescription("PTZ Down", "pan_and_tilt")
    ptz_left = CommandDescription("PTZ Left", "pan_and_tilt")
    ptz_right = CommandDescription("PTZ Right", "pan_and_tilt")
    ptz_360 = CommandDescription("PTZ 360", "pan_and_tilt")
    calibrate = CommandDescription("Calibrate", "calibrate")
    trigger_alarm = CommandDescription("Trigger Alarm")
    reset_alarm = CommandDescription("Reset Alarm")
    verify_pin = CommandDescription("Verify Pin", "verify_p_i_n")
    reboot = CommandDescription("Reboot", "stationReboot")


class EventSourceType(Enum):
    """Event type"""

    station = "station"
    device = "device"
    driver = "driver"
    server = "server"
    product = "product"
