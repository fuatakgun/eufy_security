"""Module to initialize client"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

_LOGGER: logging.Logger = logging.getLogger(__package__)


from .camera import Camera
from .const import (
    SCHEMA_VERSION,
    EventNameToHandler,
    EventSourceType,
    IncomingMessageType,
    MessageField,
    OutgoingMessageType,
    ProductType,
)
from .event import Event
from .exceptions import (
    CaptchaRequiredException,
    DeviceNotInitializedYetException,
    FailedCommandException,
    IncompatibleVersionException,
    UnexpectedMessageTypeException,
    UnknownEventSourceException,
    WebSocketConnectionErrorException,
)
from .metadata import Metadata
from .outgoing_message import OutgoingMessage
from .product import Device, Product, Station
from .web_socket_client import WebSocketClient


class ApiClient:
    """Client to communicate with eufy-security-ws over websocket connection"""

    def __init__(self, host: str, port: int, session: aiohttp.ClientSession) -> None:
        self.host: str = host
        self.port: int = port
        self.session: aiohttp.ClientSession = session
        self.loop = asyncio.get_event_loop()
        self.client: WebSocketClient = WebSocketClient(
            self.host, self.port, self.session, self._on_open, self._on_message, self._on_close, self._on_error
        )
        self.result_futures: dict[str, asyncio.Future] = {}
        self.devices: dict = None
        self.stations: dict = None
        self.captcha_future: asyncio.Future[dict] = self.loop.create_future()

    async def connect(self):
        """Set up web socket connection and set products"""
        await self.client.connect()
        await self._set_schema(SCHEMA_VERSION)
        await self._set_products()

    async def set_captcha_and_connect(self, captcha_id: str, captcha_input: str):
        """Set captcha set products"""
        await self._set_captcha(captcha_id, captcha_input)
        await asyncio.sleep(10)
        await self._set_products()

    async def _set_captcha(self, captcha_id: str, captcha_input: str) -> None:
        command_type = OutgoingMessageType.set_captcha
        command = EventSourceType.driver.name + "." + command_type.name
        await self._send_message_get_response(
            OutgoingMessage(command_type, command=command, captcha_id=captcha_id, captcha_input=captcha_input)
        )

    async def disconnect(self):
        """Disconnect the web socket and destroy it"""
        await self.client.disconnect()

    async def poll_refresh(self) -> None:
        """Poll cloud data for latest changes"""
        command_type = OutgoingMessageType.poll_refresh
        command = EventSourceType.driver.name + "." + command_type.name
        await self._send_message_get_response(OutgoingMessage(command_type, command=command))

    async def _set_schema(self, schema_version: int) -> None:
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.set_api_schema, schema_version=schema_version))

    async def _set_products(self) -> None:
        result = await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.start_listening))
        if result[MessageField.STATE.value][EventSourceType.driver.name][MessageField.CONNECTED.value] is False:
            event = await self.captcha_future
            raise CaptchaRequiredException(event.data[MessageField.CAPTCHA_ID.value], event.data[MessageField.CAPTCHA_IMG.value])

        self.devices = await self._get_product(ProductType.device, result[MessageField.STATE.value]["devices"])
        self.stations = await self._get_product(ProductType.station, result[MessageField.STATE.value]["stations"])

    async def _get_product(self, product_type: ProductType, products: list) -> dict:
        response = {}
        for serial_no in products:
            product: Product = None
            properties_result = await self._get_properties(product_type, serial_no)
            properties = properties_result[MessageField.PROPERTIES.value]
            metadata_result = await self._get_metadata(product_type, serial_no)
            metadata = metadata_result[MessageField.PROPERTIES.value]
            commands_result = await self._get_commands(product_type, serial_no)
            commands = commands_result[MessageField.COMMANDS.value]

            if product_type == ProductType.device:
                if metadata.get(MessageField.PICTURE_URL.value, None) is None:
                    product = Device(self, serial_no, properties, metadata, commands)
                else:
                    product = Camera(self, serial_no, properties, metadata, commands)
            else:
                product = Station(self, serial_no, properties, metadata, commands)

            response[serial_no] = product
        return response

    async def start_rtsp_livestream(self, product: Product):
        """Process start rtsp livestream call"""
        command_type = OutgoingMessageType.start_rtsp_livestream
        command = product.product_type.name + "." + command_type.name
        await self._send_message_get_response(OutgoingMessage(command_type, command=command, serial_no=product.serial_no))

    async def stop_rtsp_livestream(self, product: Product):
        """Process stop rtsp livestream call"""
        command_type = OutgoingMessageType.stop_rtsp_livestream
        command = product.product_type.name + "." + command_type.name
        await self._send_message_get_response(OutgoingMessage(command_type, command=command, serial_no=product.serial_no))

    async def start_p2p_livestream(self, product: Product):
        """Process start p2p livestream call"""
        command_type = OutgoingMessageType.start_livestream
        command = product.product_type.name + "." + command_type.name
        await self._send_message_get_response(OutgoingMessage(command_type, command=command, serial_no=product.serial_no))

    async def stop_p2p_livestream(self, product: Product):
        """Process stop p2p livestream call"""
        command_type = OutgoingMessageType.stop_livestream
        command = product.product_type.name + "." + command_type.name
        await self._send_message_get_response(OutgoingMessage(command_type, command=command, serial_no=product.serial_no))

    async def trigger_alarm(self, metadata: Metadata):
        """Process trigger alarm call"""
        command_type = OutgoingMessageType.trigger_alarm
        command = metadata.product.product_type.name + "." + command_type.name
        await self._send_message_get_response(
            OutgoingMessage(command_type, command=command, serial_no=metadata.product.serial_no, seconds=10)
        )

    async def reset_alarm(self, metadata: Metadata):
        """Process reset alarm call"""
        command_type = OutgoingMessageType.reset_alarm
        command = metadata.product.product_type.name + "." + command_type.name
        await self._send_message_get_response(OutgoingMessage(command_type, command=command, serial_no=metadata.product.serial_no))

    async def set_property(self, metadata: Metadata, value: Any):
        """Process set property call"""
        command_type = OutgoingMessageType.set_property
        command = metadata.product.product_type.name + "." + command_type.name
        await self._send_message_get_response(
            OutgoingMessage(command_type, command=command, serial_no=metadata.product.serial_no, name=metadata.name, value=value)
        )

    async def _get_properties(self, product_type: ProductType, serial_no: str) -> dict:
        command_type = OutgoingMessageType.get_properties
        command = product_type.name + "." + command_type.name
        message = OutgoingMessage(command_type, command=command, serial_no=serial_no)
        return await self._send_message_get_response(message)

    async def _get_metadata(self, product_type: ProductType, serial_no: str) -> dict:
        command_type = OutgoingMessageType.get_properties_metadata
        command = product_type.name + "." + command_type.name
        message = OutgoingMessage(command_type, command=command, serial_no=serial_no)
        return await self._send_message_get_response(message)

    async def _get_commands(self, product_type: ProductType, serial_no: str) -> dict:
        command_type = OutgoingMessageType.get_commands
        command = product_type.name + "." + command_type.name
        message = OutgoingMessage(command_type, command=command, serial_no=serial_no)
        return await self._send_message_get_response(message)

    async def _on_message(self, message: dict) -> None:
        message_str = str(message)[0:200]
        # message_str = str(message)
        if "livestream video data" not in message_str and "livestream audio data" not in message_str:
            _LOGGER.debug(f"_on_message - {message_str}")
        if message[MessageField.TYPE.value] == IncomingMessageType.result.name:
            future = self.result_futures.get(message[MessageField.MESSAGE_ID.value])

            if future is None:
                return

            if message[MessageField.SUCCESS.value]:
                future.set_result(message[IncomingMessageType.result.name])
                return

            future.set_exception(
                FailedCommandException(message[MessageField.MESSAGE_ID.value], message[MessageField.ERROR_CODE.value], message)
            )
        elif message[MessageField.TYPE.value] == IncomingMessageType.event.name:
            event: Event = Event(
                type=message[IncomingMessageType.event.name][IncomingMessageType.event.name], data=message[IncomingMessageType.event.name]
            )
            await self._handle_event(event)
        elif message[MessageField.TYPE.value] == IncomingMessageType.version.name:
            if SCHEMA_VERSION > message["maxSchemaVersion"]:
                raise IncompatibleVersionException(message["maxSchemaVersion"], SCHEMA_VERSION)
        else:
            raise UnexpectedMessageTypeException(message)

    async def _handle_event(self, event: Event):
        if event.data[MessageField.SOURCE.value] in [EventSourceType.station.name, EventSourceType.device.name]:
            # handle device or statino specific events through specific instances
            plural_product = event.data[MessageField.SOURCE.value] + "s"
            try:
                product = self.__dict__[plural_product][event.data[MessageField.SERIAL_NUMBER.value]]
                await product.process_event(event)
            except (KeyError, TypeError) as exc:
                raise DeviceNotInitializedYetException(event) from exc
        elif event.data[MessageField.SOURCE.value] in [EventSourceType.driver.name, EventSourceType.server.name]:
            # handle driver or server specific events locally
            await self._process_driver_event(event)
        else:
            raise UnknownEventSourceException(event)

    async def _process_driver_event(self, event: Event):
        """Process driver level events"""
        if event.type == EventNameToHandler.captcha_request.value:
            self.captcha_future.set_result(event)

    async def _on_open(self) -> None:
        _LOGGER.debug("on_open - executed")

    def _on_close(self) -> None:
        _LOGGER.debug("on_close - executed")

    async def _on_error(self, error: str) -> None:
        _LOGGER.error(f"on_error - {error}")
        raise WebSocketConnectionErrorException(error)

    async def _send_message_get_response(self, message: OutgoingMessage) -> dict:
        future: "asyncio.Future[dict]" = self.loop.create_future()
        self.result_futures[message.id] = future
        await self.send_message(message.content)
        try:
            return await future
        finally:
            self.result_futures.pop(message.id)

    async def send_message(self, message: dict) -> None:
        """send message to websocket api"""
        _LOGGER.debug(f"send_message - {message}")
        await self.client.send_message(json.dumps(message))
