"""Module to initialize client"""
from __future__ import annotations

import asyncio
from enum import Enum
import json
import logging
from typing import Any

import aiohttp

_LOGGER: logging.Logger = logging.getLogger(__package__)


from .camera import Camera
from .const import (
    SCHEMA_VERSION,
    EventNameToHandler,
    MessageField,
    ProductCommand,
    ProductType,
)
from .event import Event
from .exceptions import (
    CaptchaRequiredException,
    DeviceNotInitializedYetException,
    DriverNotConnectedError,
    FailedCommandException,
    IncompatibleVersionException,
    MultiFactorCodeRequiredException,
    UnexpectedMessageTypeException,
    UnknownEventSourceException,
    WebSocketConnectionErrorException,
)
from .outgoing_message import OutgoingMessage, OutgoingMessageType
from .product import Device, Product, Station
from .web_socket_client import WebSocketClient


class ApiClient:
    """Client to communicate with eufy-security-ws over websocket connection"""

    def __init__(self, config, session: aiohttp.ClientSession) -> None:
        self.config = config
        self.session: aiohttp.ClientSession = session
        self.loop = asyncio.get_event_loop()
        self.client: WebSocketClient = WebSocketClient(
            self.config.host, self.config.port, self.session, self._on_open, self._on_message, self._on_close, self._on_error
        )
        self.result_futures: dict[str, asyncio.Future] = {}
        self.devices: dict = None
        self.stations: dict = None
        self.captcha_future: asyncio.Future[dict] = self.loop.create_future()
        self.mfa_future: asyncio.Future[dict] = self.loop.create_future()

    async def ws_connect(self):
        """set initial websocket connection"""
        await self.client.connect()

    async def connect(self):
        """Set up web socket connection and set products"""
        await self.ws_connect()
        await self._set_schema(SCHEMA_VERSION)
        await self._set_products()

    async def set_captcha_and_connect(self, captcha_id: str, captcha_input: str):
        """Set captcha set products"""
        await self._set_captcha(captcha_id, captcha_input)
        await asyncio.sleep(10)
        await self._set_products()

    async def set_mfa_and_connect(self, mfa_input: str):
        """Set captcha set products"""
        await self._set_mfa_code(mfa_input)
        await asyncio.sleep(10)
        await self._set_products()

    async def _set_captcha(self, captcha_id: str, captcha_input: str) -> None:
        command_type = OutgoingMessageType.set_captcha
        command = EventSourceType.driver.name + "." + command_type.name
        await self._send_message_get_response(
            OutgoingMessage(command_type, command=command, captcha_id=captcha_id, captcha_input=captcha_input)
        )

    async def _set_mfa_code(self, mfa_input: str) -> None:
        command_type = OutgoingMessageType.set_verify_code
        command = EventSourceType.driver.name + "." + command_type.name
        await self._send_message_get_response(OutgoingMessage(command_type, command=command, verify_code=mfa_input))

    async def _connect_driver(self) -> None:
        command_type = OutgoingMessageType.driver_connect
        command = EventSourceType.driver.name + "." + "connect"
        await self._send_message_get_response(OutgoingMessage(command_type, command=command))

    async def _set_schema(self, schema_version: int) -> None:
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.set_api_schema, schema_version=schema_version))

    async def _set_products(self) -> None:
        result = await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.start_listening))
        if result[MessageField.STATE.value][EventSourceType.driver.name][MessageField.CONNECTED.value] is False:
            try:
                await asyncio.wait_for(self.captcha_future, timeout=5)
                event = self.captcha_future.result()
                raise CaptchaRequiredException(event.data[MessageField.CAPTCHA_ID.value], event.data[MessageField.CAPTCHA_IMG.value])
            except (asyncio.exceptions.TimeoutError, asyncio.exceptions.CancelledError):
                pass

            # driver is not connected and there is no captcha event, so it is probably mfa
            # reconnect driver to get mfa event
            try:
                await asyncio.wait_for(self.mfa_future, timeout=5)
                event = self.mfa_future.result()
                raise MultiFactorCodeRequiredException()
            except (asyncio.exceptions.TimeoutError, asyncio.exceptions.CancelledError) as exc:
                await self._connect_driver()
                raise DriverNotConnectedError() from exc

        self.devices = await self._get_product(ProductType.device, result[MessageField.STATE.value]["devices"])
        self.stations = await self._get_product(ProductType.station, result[MessageField.STATE.value]["stations"])

    async def _get_product(self, product_type: ProductType, products: list) -> dict:
        response = {}
        for serial_no in products:
            product: Product = None
            properties = await self._get_properties(product_type, serial_no)
            metadata = await self._get_metadata(product_type, serial_no)
            commands = await self._get_commands(product_type, serial_no)

            if product_type == ProductType.device:
                if ProductCommand.start_livestream.name in commands:
                    is_rtsp_streaming = await self._get_is_rtsp_streaming(product_type, serial_no)
                    is_p2p_streaming = await self._get_is_p2p_streaming(product_type, serial_no)
                    voices = await self._get_voices(product_type, serial_no)
                    product = Camera(
                        self, serial_no, properties, metadata, commands, self.config, is_rtsp_streaming, is_p2p_streaming, voices
                    )
                else:
                    product = Device(self, serial_no, properties, metadata, commands)
            else:
                product = Station(self, serial_no, properties, metadata, commands)

            response[serial_no] = product
        return response

    async def _get_is_rtsp_streaming(self, product_type: ProductType, serial_no: str) -> bool:
        command_type = OutgoingMessageType.is_rtsp_livestreaming
        command = product_type.name + "." + command_type.name
        result = await self._send_message_get_response(OutgoingMessage(command_type, command=command, serial_no=serial_no))
        return result[MessageField.LIVE_STREAMING.value]

    async def _get_is_p2p_streaming(self, product_type: ProductType, serial_no: str) -> bool:
        command_type = OutgoingMessageType.is_livestreaming
        command = product_type.name + "." + command_type.name
        result = await self._send_message_get_response(OutgoingMessage(command_type, command=command, serial_no=serial_no))
        return result[MessageField.LIVE_STREAMING.value]

    async def pan_and_tilt(self, product_type: ProductType, serial_no: str, direction: int) -> None:
        """Process start pan tilt rotate zoom"""
        command_type = OutgoingMessageType.pan_and_tilt
        command = product_type.name + "." + command_type.name
        await self._send_message_get_response(OutgoingMessage(command_type, command=command, serial_no=serial_no, direction=direction))

    async def quick_response(self, product_type: ProductType, serial_no: str, voice_id: int) -> None:
        """Process start pan tilt rotate zoom"""
        command_type = OutgoingMessageType.quick_response
        command = product_type.name + "." + command_type.name
        await self._send_message_get_response(OutgoingMessage(command_type, command=command, serial_no=serial_no, voice_id=voice_id))

    async def start_rtsp_livestream(self, product_type: ProductType, serial_no: str) -> None:
        """Process start rtsp livestream call"""
        command_type = OutgoingMessageType.start_rtsp_livestream
        command = product_type.name + "." + command_type.name
        await self._send_message_get_response(OutgoingMessage(command_type, command=command, serial_no=serial_no))

    async def stop_rtsp_livestream(self, product_type: ProductType, serial_no: str) -> None:
        """Process stop rtsp livestream call"""
        command_type = OutgoingMessageType.stop_rtsp_livestream
        command = product_type.name + "." + command_type.name
        await self._send_message_get_response(OutgoingMessage(command_type, command=command, serial_no=serial_no))

    async def start_livestream(self, product_type: ProductType, serial_no: str) -> None:
        """Process start p2p livestream call"""
        command_type = OutgoingMessageType.start_livestream
        command = product_type.name + "." + command_type.name
        await self._send_message_get_response(OutgoingMessage(command_type, command=command, serial_no=serial_no))

    async def stop_livestream(self, product_type: ProductType, serial_no: str) -> None:
        """Process stop p2p livestream call"""
        command_type = OutgoingMessageType.stop_livestream
        command = product_type.name + "." + command_type.name
        await self._send_message_get_response(OutgoingMessage(command_type, command=command, serial_no=serial_no))

    async def trigger_alarm(self, product_type: ProductType, serial_no: str, duration: int) -> None:
        """Process trigger alarm call"""
        command_type = OutgoingMessageType.trigger_alarm
        command = product_type.name + "." + command_type.name
        await self._send_message_get_response(OutgoingMessage(command_type, command=command, serial_no=serial_no, seconds=duration))

    async def reset_alarm(self, product_type: ProductType, serial_no: str) -> None:
        """Process reset alarm call"""
        command_type = OutgoingMessageType.reset_alarm
        command = product_type.name + "." + command_type.name
        await self._send_message_get_response(OutgoingMessage(command_type, command=command, serial_no=serial_no))

    async def set_property(self, product_type: ProductType, serial_no: str, name: str, value: Any) -> None:
        """Process set property call"""
        command_type = OutgoingMessageType.set_property
        command = product_type.name + "." + command_type.name
        await self._send_message_get_response(OutgoingMessage(command_type, command=command, serial_no=serial_no, name=name, value=value))

    async def _get_voices(self, product_type: ProductType, serial_no: str) -> dict:
        command_type = OutgoingMessageType.get_voices
        command = product_type.name + "." + command_type.name
        result = await self._send_message_get_response(OutgoingMessage(command_type, command=command, serial_no=serial_no))
        return result[MessageField.VOICES.value]

    async def _get_properties(self, product_type: ProductType, serial_no: str) -> dict:
        command_type = OutgoingMessageType.get_properties
        command = product_type.name + "." + command_type.name
        result = await self._send_message_get_response(OutgoingMessage(command_type, command=command, serial_no=serial_no))
        return result[MessageField.PROPERTIES.value]

    async def _get_metadata(self, product_type: ProductType, serial_no: str) -> dict:
        command_type = OutgoingMessageType.get_properties_metadata
        command = product_type.name + "." + command_type.name
        result = await self._send_message_get_response(OutgoingMessage(command_type, command=command, serial_no=serial_no))
        return result[MessageField.PROPERTIES.value]

    async def _get_commands(self, product_type: ProductType, serial_no: str) -> dict:
        command_type = OutgoingMessageType.get_commands
        command = product_type.name + "." + command_type.name
        result = await self._send_message_get_response(OutgoingMessage(command_type, command=command, serial_no=serial_no))
        return result[MessageField.COMMANDS.value]

    async def _on_message(self, message: dict) -> None:
        # message_str = str(message)[0:200]
        message_str = str(message)
        if "livestream video data" not in message_str and "livestream audio data" not in message_str:
            _LOGGER.debug(f"_on_message - {message_str}")
        if message[MessageField.TYPE.value] == IncomingMessageType.result.name:
            future = self.result_futures.get(message.get(MessageField.MESSAGE_ID.value, -1), None)

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
        if event.type == EventNameToHandler.verify_code.value:
            self.mfa_future.set_result(event)

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

    async def poll_refresh(self) -> None:
        """Poll cloud data for latest changes"""
        command_type = OutgoingMessageType.poll_refresh
        command = EventSourceType.driver.name + "." + command_type.name
        await self._send_message_get_response(OutgoingMessage(command_type, command=command))

    async def disconnect(self):
        """Disconnect the web socket and destroy it"""
        await self.client.disconnect()


class IncomingMessageType(Enum):
    """Incoming message types"""

    version = "version"
    result = "result"
    event = "event"


class EventSourceType(Enum):
    """Event type"""

    station = "station"
    device = "device"
    driver = "driver"
    server = "server"
