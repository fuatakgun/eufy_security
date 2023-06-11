from dataclasses import dataclass, field
import logging

from .const import MessageField, PropertyType
from typing import Any

_LOGGER: logging.Logger = logging.getLogger(__package__)


@dataclass
class Metadata:
    """Property Metadata"""

    name: str
    label: str
    readable: bool
    writeable: bool
    type: str
    unit: str
    min: int
    max: int
    product: Any
    command: str
    states: dict = field(default_factory=dict)

    @classmethod
    def parse(cls, product: Any, data: dict):
        """generate Metadata from data dictionary"""

        return cls(
            name=data[MessageField.NAME.value],
            label=data[MessageField.LABEL.value],
            readable=data.get(MessageField.READABLE.value, True),
            writeable=data.get(MessageField.WRITEABLE.value, False),
            type=PropertyType[data.get(MessageField.TYPE.value, "string")],
            unit=data.get(MessageField.UNIT.value, None),
            min=data.get(MessageField.MIN.value, None),
            max=data.get(MessageField.MAX.value, None),
            product=product,
            command=data.get(MessageField.COMMAND.value, None),
            states=data.get(MessageField.STATES.value, None),
        )
