"""Define all constants for module."""
from enum import Enum, auto
import logging

_LOGGER: logging.Logger = logging.getLogger(__package__)

SCHEMA_VERSION = 15


class IncomingMessageType(Enum):
    """Incoming message types"""

    version = "version"
    result = "result"
    event = "event"


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


class OutgoingMessageToParameter(Enum):
    """Outgoing message fields to runtime parameters"""

    schemaVersion = "schema_version"
    serialNumber = "serial_no"
    name = "name"
    value = "value"
    seconds = "seconds"
    captchaId = "captcha_id"
    captcha = "captcha_input"


class OutgoingMessageType(Enum):
    """Outgoing message types"""

    set_api_schema = {MessageField.COMMAND.value: auto(), MessageField.SCHEMA_VERSION.value: MessageField.BIND_AT_RUNTIME}
    start_listening = {MessageField.COMMAND.value: auto()}
    get_properties_metadata = {MessageField.COMMAND.value: auto(), MessageField.SERIAL_NUMBER.value: MessageField.BIND_AT_RUNTIME}
    get_properties = {MessageField.COMMAND.value: auto(), MessageField.SERIAL_NUMBER.value: MessageField.BIND_AT_RUNTIME}
    get_commands = {MessageField.COMMAND.value: auto(), MessageField.SERIAL_NUMBER.value: MessageField.BIND_AT_RUNTIME}
    poll_refresh = {MessageField.COMMAND.value: auto()}
    set_property = {
        MessageField.COMMAND.value: auto(),
        MessageField.SERIAL_NUMBER.value: MessageField.BIND_AT_RUNTIME,
        MessageField.NAME.value: MessageField.BIND_AT_RUNTIME,
        MessageField.VALUE.value: MessageField.BIND_AT_RUNTIME,
    }
    trigger_alarm = {
        MessageField.COMMAND.value: auto(),
        MessageField.SERIAL_NUMBER.value: MessageField.BIND_AT_RUNTIME,
        MessageField.SECONDS.value: MessageField.BIND_AT_RUNTIME,
    }
    reset_alarm = {MessageField.COMMAND.value: auto(), MessageField.SERIAL_NUMBER.value: MessageField.BIND_AT_RUNTIME}
    start_rtsp_livestream = {
        MessageField.COMMAND.value: auto(),
        MessageField.SERIAL_NUMBER.value: MessageField.BIND_AT_RUNTIME,
    }
    stop_rtsp_livestream = {
        MessageField.COMMAND.value: auto(),
        MessageField.SERIAL_NUMBER.value: MessageField.BIND_AT_RUNTIME,
    }
    start_livestream = {
        MessageField.COMMAND.value: auto(),
        MessageField.SERIAL_NUMBER.value: MessageField.BIND_AT_RUNTIME,
    }
    stop_livestream = {
        MessageField.COMMAND.value: auto(),
        MessageField.SERIAL_NUMBER.value: MessageField.BIND_AT_RUNTIME,
    }
    set_captcha = {
        MessageField.COMMAND.value: auto(),
        MessageField.CAPTCHA_ID.value: MessageField.BIND_AT_RUNTIME,
        MessageField.CAPTCHA_IMG.value: MessageField.BIND_AT_RUNTIME,
    }


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


class EventSourceType(Enum):
    """Event type"""

    station = "station"
    device = "device"
    driver = "driver"
    server = "server"


class PropertyType(Enum):
    """Property type"""

    number = "number"
    string = "string"
    boolean = "boolean"


class StreamStatus(Enum):
    """Stream status"""

    IDLE = "idle"
    PREPARING = "preparing"
    STREAMING = "streaming"


class StreamProvider(Enum):
    """Stream provider"""

    RTSP = "{rtsp_stream_url}"  # replace with rtsp url from device
    P2P = "rtsp://192.168.178.119:8554/{serial_no}"  # replace with stream name
