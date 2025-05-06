from enum import Enum, auto
import logging
import uuid

from .const import MessageField, EventSourceType

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
    position = "position"
    verifyCode = "verify_code"
    voiceId = "voice_id"
    snoozeTime = "snooze_time"
    snoozeChime = "snooze_chime"
    snoozeMotion = "snooze_motion"
    snoozeHomebase = "snooze_homebase"
    level = "log_level"
    ringtone = "ringtone"
    pin = "pin"


class OutgoingMessageType(Enum):
    """Outgoing message types"""

    # server level commands
    start_listening = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.server}
    set_api_schema = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.server, MessageField.SCHEMA_VERSION: None}

    # driver level commands
    connect = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.driver}
    disconnect = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.driver}
    set_log_level = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.driver, MessageField.LOG_LEVEL: None}
    poll_refresh = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.driver}
    set_captcha = {
        MessageField.DUMMY: auto(),
        MessageField.DOMAIN: EventSourceType.driver,
        MessageField.CAPTCHA_ID: None,
        MessageField.CAPTCHA_IMG: None,
    }
    set_verify_code = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.driver, MessageField.VERIFY_CODE: None}
    get_video_events = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.driver, MessageField.MAX_RESULTS: None}

    # product (both device and station) level commands
    get_properties_metadata = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.product}
    get_properties = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.product}
    get_commands = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.product}
    set_property = {
        MessageField.DUMMY: auto(),
        MessageField.DOMAIN: EventSourceType.product,
        MessageField.NAME: None,
        MessageField.VALUE: None,
    }
    trigger_alarm = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.product, MessageField.SECONDS: None}
    reset_alarm = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.product}

    # device level commands
    pan_and_tilt = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.device, MessageField.DIRECTION: None}
    preset_position = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.device, MessageField.POSITION: None}
    save_preset_position = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.device, MessageField.POSITION: None}
    delete_preset_position = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.device, MessageField.POSITION: None}
    calibrate = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.device}
    start_rtsp_livestream = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.device}
    stop_rtsp_livestream = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.device}
    is_rtsp_livestreaming = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.device}
    start_livestream = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.device}
    stop_livestream = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.device}
    is_livestreaming = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.device}
    get_voices = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.device}
    quick_response = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.device, MessageField.VOICE_ID: None}
    snooze = {
        MessageField.DUMMY: auto(),
        MessageField.DOMAIN: EventSourceType.device,
        MessageField.SNOOZE_TIME: None,
        MessageField.SNOOZE_CHIME: None,
        MessageField.SNOOZE_MOTION: None,
        MessageField.SNOOZE_HOMEBASE: None,
    }
    verify_pin = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.device, MessageField.PIN: None}
    unlock = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.device}

    # station level commands
    chime = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.station, MessageField.RINGTONE: None}
    reboot = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.station}
    is_connected = {MessageField.DUMMY: auto(), MessageField.DOMAIN: EventSourceType.station}


class OutgoingMessage:
    """Outgoing message"""

    def __init__(self, message_type: OutgoingMessageType, **kwargs) -> None:
        self._type = message_type
        self._message = {}

        for key in message_type.value.keys():
            try:
                self._message[key.value] = kwargs.get(OutgoingMessageToParameter[key.value].value)
            except KeyError:
                pass

        default_domain = message_type.value[MessageField.DOMAIN]
        if default_domain in [EventSourceType.product, EventSourceType.station, EventSourceType.device]:
            self._message[MessageField.SERIAL_NO.value] = kwargs.get(OutgoingMessageToParameter[MessageField.SERIAL_NO.value].value)

        domain = default_domain.value if default_domain != EventSourceType.product else kwargs.get(MessageField.DOMAIN.value, "")
        command = self.type.name if domain == EventSourceType.server.value else domain + "." + self.type.name
        _LOGGER.debug(f"domain - {domain} - {default_domain} - {command} - {kwargs} - {self._message}")
        self._message[MessageField.COMMAND.value] = command
        self._message[MessageField.MESSAGE_ID.value] = self.command + "." + uuid.uuid4().hex
        _LOGGER.debug(self._message)

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
