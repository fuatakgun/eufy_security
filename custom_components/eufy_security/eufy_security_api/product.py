from collections.abc import Callable
import logging
from typing import Any

from .const import EventNameToHandler, MessageField, ProductType, ProductCommand
from .event import Event
from .metadata import Metadata

_LOGGER: logging.Logger = logging.getLogger(__package__)


class Product:
    """Product"""

    def __init__(self, api, product_type: ProductType, serial_no: str, properties: dict, metadata: dict, commands: []) -> None:
        self.api = api
        self.product_type = product_type
        self.serial_no = serial_no

        self.name: str = None
        self.model: str = None
        self.hardware_version: str = None
        self.software_version: str = None

        self.properties: dict = None
        self.metadata: dict = None
        self.metadata_org = metadata
        self.commands = commands

        self.state_update_listener: Callable = None

        self._set_properties(properties)
        self._set_metadata(metadata)

    def _set_properties(self, properties: dict) -> None:
        self.properties = properties
        self.name = properties[MessageField.NAME.value]
        self.model = properties[MessageField.MODEL.value]
        self.hardware_version = properties[MessageField.HARDWARE_VERSION.value]
        self.software_version = properties[MessageField.SOFTWARE_VERSION.value]

    def _set_metadata(self, metadata: dict) -> None:
        self.metadata = {}
        for key, value in metadata.items():
            self.metadata[key] = Metadata.parse(self, value)

    def set_state_update_listener(self, listener: Callable):
        """Set listener function when state changes"""
        self.state_update_listener = listener

    async def set_property(self, metadata, value: Any):
        """Process set property call"""
        await self.api.set_property(self.product_type, self.serial_no, metadata.name, value)

    async def trigger_alarm(self, duration: int = 10):
        """Process trigger alarm call"""
        await self.api.trigger_alarm(self.product_type, self.serial_no, duration)

    async def reset_alarm(self):
        """Process reset alarm call"""
        await self.api.reset_alarm(self.product_type, self.serial_no)

    def has(self, property_name: str) -> bool:
        """Checks if product has required property"""
        return False if self.properties.get(property_name, None) is None else True

    async def process_event(self, event: Event):
        """Act on received event"""
        handler_func = None

        try:
            handler = EventNameToHandler(event.type)
            handler_func = getattr(self, f"_handle_{handler.name}", None)
        except ValueError:
            # event is not acted on, skip it
            return

        if handler_func is not None:
            await handler_func(event)

        if self.state_update_listener is not None:
            callback_func = self.state_update_listener
            callback_func()

    async def _handle_property_changed(self, event: Event):
        self.properties[event.data[MessageField.NAME.value]] = event.data[MessageField.VALUE.value]

    @property
    def is_camera(self):
        """checks if Product is camera"""
        return True if ProductCommand.start_livestream.name in self.commands else False


class Device(Product):
    """Device as Physical Product"""

    def __init__(self, api, serial_no: str, properties: dict, metadata: dict, commands: []) -> None:
        super().__init__(api, ProductType.device, serial_no, properties, metadata, commands)


class Station(Product):
    """Station as Physical Product"""

    def __init__(self, api, serial_no: str, properties: dict, metadata: dict, commands: []) -> None:
        super().__init__(api, ProductType.station, serial_no, properties, metadata, commands)
