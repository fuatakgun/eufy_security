import asyncio
from collections.abc import Callable
import logging
from typing import Any

from .const import EventNameToHandler, MessageField, ProductCommand, ProductType, UNSUPPORTED
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
        self.connected = True

        self.state_update_listener: Callable = None

        self._set_properties(properties)
        self._set_metadata(metadata)

        self.pin_verified_future = None

    def _set_properties(self, properties: dict) -> None:
        self.properties = properties
        _LOGGER.debug(f"_set_properties -{self.serial_no} - {str(properties)[0:5000]}")
        self.name = properties.get(MessageField.NAME.value, "UNSUPPORTED")
        self.model = properties.get(MessageField.MODEL.value, "UNSUPPORTED")
        self.hardware_version = properties.get(MessageField.HARDWARE_VERSION.value, "UNSUPPORTED")
        self.software_version = properties.get(MessageField.SOFTWARE_VERSION.value, "UNSUPPORTED")

    def _set_metadata(self, metadata: dict) -> None:
        self.metadata = {}

        for key, value in metadata.items():
            metadata = Metadata.parse(self, value)

            if key == "motionDetected" and metadata.name == "motionDetection":
                metadata.name = key

            self.metadata[key] = metadata

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

    async def snooze(self, snooze_time: int, snooze_chime: bool, snooze_motion: bool, snooze_homebase: bool) -> None:
        """Process snooze call"""
        await self.api.snooze(self.product_type, self.serial_no, snooze_time, snooze_chime, snooze_motion, snooze_homebase)
        await self.api.poll_refresh()

    async def unlock(self, code: str) -> bool:
        """Process unlock the safe"""
        self.pin_verified_future = asyncio.get_running_loop().create_future()
        await self.api.verify_pin(self.product_type, self.serial_no, code)
        await asyncio.wait_for(self.pin_verified_future, timeout=5)
        event = self.pin_verified_future.result()
        if event.data[MessageField.SUCCESSFULL.value] is False:
            return False
        await self.api.unlock(self.product_type, self.serial_no)
        return True

    async def process_event(self, event: Event):
        """Act on received event"""
        handler_func = None

        try:
            handler = EventNameToHandler(event.type)
            handler_func = getattr(self, f"_handle_{handler.name}", None)
        except ValueError:
            # event is not acted on, skip it
            _LOGGER.debug(f"event not handled -{self.serial_no} - {event}")
            return

        if handler_func is not None:
            await handler_func(event)

        if self.state_update_listener is not None:
            callback_func = self.state_update_listener
            callback_func()

    async def _handle_property_changed(self, event: Event):
        self.properties[event.data[MessageField.NAME.value]] = event.data[MessageField.VALUE.value]

    async def _handle_pin_verified(self, event: Event):
        self.pin_verified_future.set_result(event)

    async def _handle_connected(self, event: Event):
        self.properties[MessageField.CONNECTED.value] = True

    async def _handle_disconnected(self, event: Event):
        self.properties[MessageField.CONNECTED.value] = False

    async def _handle_connection_error(self, event: Event):
        self.properties[MessageField.CONNECTED.value] = False

    @property
    def is_camera(self):
        """checks if Product is camera"""
        return True if ProductCommand.start_livestream.value.command in self.commands else False

    @property
    def is_safe_lock(self):
        """checks if Product is safe lock"""
        return True if ProductCommand.verify_pin.value.command in self.commands else False

    def has(self, property_name: str) -> bool:
        """Checks if product has required property"""
        return False if self.properties.get(property_name, None) is None else True


class Device(Product):
    """Device as Physical Product"""

    def __init__(self, api, serial_no: str, properties: dict, metadata: dict, commands: []) -> None:
        super().__init__(api, ProductType.device, serial_no, properties, metadata, commands)


class Station(Product):
    """Station as Physical Product"""

    def __init__(self, api, serial_no: str, properties: dict, metadata: dict, commands: []) -> None:
        super().__init__(api, ProductType.station, serial_no, properties, metadata, commands)

    async def chime(self, ringtone: int) -> None:
        """Quick response message to camera"""
        await self.api.chime(self.product_type, self.serial_no, ringtone)

    async def reboot(self) -> None:
        """Reboot station"""
        await self.api.reboot(self.product_type, self.serial_no)
