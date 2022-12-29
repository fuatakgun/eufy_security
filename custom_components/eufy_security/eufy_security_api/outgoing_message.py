from enum import Enum, auto
import logging
import uuid

from .const import MessageField

_LOGGER: logging.Logger = logging.getLogger(__package__)


class OutgoingMessageToParameter(Enum):
    """Outgoing message fields to runtime parameters"""

    schemaVersion = "schema_version"
    serialNumber = "serial_no"
    name = "name"
    value = "value"
    seconds = "seconds"
    captchaId = "captcha_id"
    captcha = "captcha_input"
    direction = "direction"
    verifyCode = "verify_code"
    voiceId = "voice_id"
    snoozeTime = "snooze_time"
    snoozeChime = "snooze_chime"
    snoozeMotion = "snooze_motion"
    snoozeHomebase = "snooze_homebase"


class OutgoingMessageType(Enum):
    """Outgoing message types"""

    driver_connect = {MessageField.COMMAND.value: auto()}
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
    pan_and_tilt = {
        MessageField.COMMAND.value: auto(),
        MessageField.SERIAL_NUMBER.value: MessageField.BIND_AT_RUNTIME,
        MessageField.DIRECTION.value: MessageField.BIND_AT_RUNTIME,
    }
    reset_alarm = {MessageField.COMMAND.value: auto(), MessageField.SERIAL_NUMBER.value: MessageField.BIND_AT_RUNTIME}
    start_rtsp_livestream = {MessageField.COMMAND.value: auto(), MessageField.SERIAL_NUMBER.value: MessageField.BIND_AT_RUNTIME}
    stop_rtsp_livestream = {MessageField.COMMAND.value: auto(), MessageField.SERIAL_NUMBER.value: MessageField.BIND_AT_RUNTIME}
    is_rtsp_livestreaming = {MessageField.COMMAND.value: auto(), MessageField.SERIAL_NUMBER.value: MessageField.BIND_AT_RUNTIME}
    start_livestream = {MessageField.COMMAND.value: auto(), MessageField.SERIAL_NUMBER.value: MessageField.BIND_AT_RUNTIME}
    stop_livestream = {MessageField.COMMAND.value: auto(), MessageField.SERIAL_NUMBER.value: MessageField.BIND_AT_RUNTIME}
    is_livestreaming = {MessageField.COMMAND.value: auto(), MessageField.SERIAL_NUMBER.value: MessageField.BIND_AT_RUNTIME}
    set_captcha = {
        MessageField.COMMAND.value: auto(),
        MessageField.CAPTCHA_ID.value: MessageField.BIND_AT_RUNTIME,
        MessageField.CAPTCHA_IMG.value: MessageField.BIND_AT_RUNTIME,
    }
    set_verify_code = {MessageField.COMMAND.value: auto(), MessageField.VERIFY_CODE.value: MessageField.BIND_AT_RUNTIME}
    get_voices = {MessageField.COMMAND.value: auto(), MessageField.SERIAL_NUMBER.value: MessageField.BIND_AT_RUNTIME}
    quick_response = {
        MessageField.COMMAND.value: auto(),
        MessageField.SERIAL_NUMBER.value: MessageField.BIND_AT_RUNTIME,
        MessageField.VOICE_ID.value: MessageField.BIND_AT_RUNTIME,
    }
    snooze = {
        MessageField.COMMAND.value: auto(),
        MessageField.SERIAL_NUMBER.value: MessageField.BIND_AT_RUNTIME,
        MessageField.SNOOZE_TIME.value: MessageField.BIND_AT_RUNTIME,
        MessageField.SNOOZE_CHIME.value: MessageField.BIND_AT_RUNTIME,
        MessageField.SNOOZE_MOTION.value: MessageField.BIND_AT_RUNTIME,
        MessageField.SNOOZE_HOMEBASE.value: MessageField.BIND_AT_RUNTIME,
    }


class OutgoingMessage:
    """Outgoing message"""

    def __init__(self, message_type: OutgoingMessageType, **kwargs) -> None:
        self._type = message_type
        self._message = self.type.value.copy()
        self._message[MessageField.COMMAND.value] = kwargs.get("command", self.type.name)
        self._message[MessageField.MESSAGE_ID.value] = kwargs.get("id", self.command + "." + uuid.uuid4().hex)

        for key, value in self._message.items():
            if value == MessageField.BIND_AT_RUNTIME:
                self._message[key] = kwargs.get(OutgoingMessageToParameter[key].value)

    @property
    def id(self) -> str:
        """Message Id"""
        return self.content[MessageField.MESSAGE_ID.value]

    @property
    def command(self) -> str:
        """Message Command"""
        return self.content[MessageField.COMMAND.value]

    @property
    def content(self) -> str:
        """Message Content"""
        return self._message

    @property
    def type(self) -> OutgoingMessageType:
        """Message Type"""
        return self._type
