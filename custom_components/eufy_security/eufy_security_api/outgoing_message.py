import logging
import uuid

from .const import MessageField, OutgoingMessageToParameter, OutgoingMessageType

_LOGGER: logging.Logger = logging.getLogger(__package__)


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
