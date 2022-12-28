"""Define all constants for module."""
from enum import Enum
import logging

_LOGGER: logging.Logger = logging.getLogger(__package__)

SCHEMA_VERSION = 15


class MessageField(Enum):
    """Incoming or outgoing message field types"""

    # general fields
    MESSAGE_ID = "messageId"
    ERROR_CODE = "errorCode"
    COMMAND = "command"
    TYPE = "type"
    SUCCESS = "success"
    STATE = "state"
    CONNECTED = "connected"
    SOURCE = "source"
    SCHEMA_VERSION = "schemaVersion"
    BIND_AT_RUNTIME = "bindAtRuntime"
    SERIAL_NUMBER = "serialNumber"
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

    # alarm control panel specific
    CURRENT_MODE = "currentMode"
    GUARD_MODE = "guardMode"
    SECONDS = "seconds"

    # camera specific
    PICTURE_URL = "pictureUrl"
    DIRECTION = "direction"
    LIVE_STREAMING = "livestreaming"
    VOICES = "voices"
    VOICE_ID = "voiceId"


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


class ProductType(Enum):
    """Product type"""

    station = "station"
    device = "device"


class PropertyType(Enum):
    """Property type"""

    number = "number"
    string = "string"
    boolean = "boolean"


class ProductCommand(Enum):
    """Important Product Commands"""

    start_livestream = "Start P2P Livestream"
