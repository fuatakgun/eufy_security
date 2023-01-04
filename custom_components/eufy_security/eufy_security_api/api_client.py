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
        self._config = config
        self._client: WebSocketClient = WebSocketClient(
            self._config.host, self._config.port, session, self._on_open, self._on_message, self._on_close, self._on_error
        )
        self._result_futures: dict[str, asyncio.Future] = {}
        self._devices: dict = None
        self._stations: dict = None
        self._captcha_future: asyncio.Future[dict] = asyncio.get_event_loop().create_future()
        self._mfa_future: asyncio.Future[dict] = asyncio.get_event_loop().create_future()

    @property
    def devices(self) -> dict:
        """ initialized devices """
        return self._devices

    @property
    def stations(self) -> dict:
        """ initialized stations """
        return self._stations

    async def ws_connect(self):
        """set initial websocket connection"""
        await self._client.connect()

    async def connect(self):
        """Set up web socket connection and set products"""
        await self.ws_connect()
        await self._set_schema(SCHEMA_VERSION)
        await self._set_products()

    async def _check_interactive_mode(self):
        # driver is not connected, wait for captcha event
        try:
            _LOGGER.debug(f"_start_listening 2")
            await asyncio.wait_for(self._captcha_future, timeout=10)
            event = self._captcha_future.result()
            raise CaptchaRequiredException(event.data[MessageField.CAPTCHA_ID.value], event.data[MessageField.CAPTCHA_IMG.value])
        except (asyncio.exceptions.TimeoutError, asyncio.exceptions.CancelledError):
            pass
        _LOGGER.debug(f"_start_listening 2")
        # driver is not connected and captcha exception is not thrown, wait for mfa event
        try:
            _LOGGER.debug(f"_start_listening 3")
            await asyncio.wait_for(self._mfa_future, timeout=5)
            event = self._mfa_future.result()
            raise MultiFactorCodeRequiredException()
        except (asyncio.exceptions.TimeoutError, asyncio.exceptions.CancelledError) as exc:
            _LOGGER.debug(f"_start_listening 4")
            await self._connect_driver()
            raise DriverNotConnectedError() from exc

    async def _set_products(self) -> None:
        _LOGGER.debug(f"_start_listening 1")
        self._captcha_future = asyncio.get_event_loop().create_future()
        self._mfa_future = asyncio.get_event_loop().create_future()
        result = await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.start_listening))
        if result[MessageField.STATE.value][EventSourceType.driver.name][MessageField.CONNECTED.value] is False:
            await self._check_interactive_mode()

        self._devices = await self._get_product(ProductType.device, result[MessageField.STATE.value]["devices"])
        self._stations = await self._get_product(ProductType.station, result[MessageField.STATE.value]["stations"])

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
                        self, serial_no, properties, metadata, commands, self._config, is_rtsp_streaming, is_p2p_streaming, voices
                    )
                else:
                    product = Device(self, serial_no, properties, metadata, commands)
            else:
                product = Station(self, serial_no, properties, metadata, commands)

            response[serial_no] = product
        return response

    async def set_captcha_and_connect(self, captcha_id: str, captcha_input: str):
        """Set captcha set products"""
        await self._set_captcha(captcha_id, captcha_input)
        await asyncio.sleep(10)
        await self._set_products()

    async def set_mfa_and_connect(self, mfa_input: str):
        """Set mfa code set products"""
        await self._set_mfa_code(mfa_input)
        await asyncio.sleep(10)
        await self._set_products()

    # general api commands
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

    async def set_log_level(self, log_level: str) -> None:
        """set log level of websocket server"""
        command_type = OutgoingMessageType.set_log_level
        command = EventSourceType.driver.name + "." + "connect"
        await self._send_message_get_response(OutgoingMessage(command_type, command=command, log_level=log_level))

    # device and station functions
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
        """Process quick response for doorbell"""
        command_type = OutgoingMessageType.quick_response
        command = product_type.name + "." + command_type.name
        await self._send_message_get_response(OutgoingMessage(command_type, command=command, serial_no=serial_no, voice_id=voice_id))

    async def chime(self, product_type: ProductType, serial_no: str, ringtone: int) -> None:
        """Process chme call"""
        command_type = OutgoingMessageType.chime
        command = product_type.name + "." + command_type.name
        await self._send_message_get_response(OutgoingMessage(command_type, command=command, serial_no=serial_no, ringtone=ringtone))

    async def snooze(
        self, product_type: ProductType, serial_no: str, snooze_time: int, snooze_chime: bool, snooze_motion: bool, snooze_homebase: bool
    ) -> None:
        """Process snooze for devices ans stations"""
        command_type = OutgoingMessageType.snooze
        command = product_type.name + "." + command_type.name
        await self._send_message_get_response(
            OutgoingMessage(
                command_type,
                command=command,
                serial_no=serial_no,
                snooze_time=snooze_time,
                snooze_chime=snooze_chime,
                snooze_motion=snooze_motion,
                snooze_homebase=snooze_homebase,
            )
        )

    async def verify_pin(self, product_type: ProductType, serial_no: str, pin: str) -> None:
        """verify pin for safe product"""
        command_type = OutgoingMessageType.verify_pin
        command = product_type.name + "." + command_type.name
        await self._send_message_get_response(OutgoingMessage(command_type, command=command, serial_no=serial_no, pin=pin))

    async def unlock(self, product_type: ProductType, serial_no: str) -> None:
        """unlock for safe product"""
        command_type = OutgoingMessageType.unlock
        command = product_type.name + "." + command_type.name
        await self._send_message_get_response(OutgoingMessage(command_type, command=command, serial_no=serial_no))

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
        message_str = str(message)[0:200]
        message_str = str(message)
        if "livestream video data" not in message_str and "livestream audio data" not in message_str:
            _LOGGER.debug(f"_on_message - {message_str}")
        if message[MessageField.TYPE.value] == IncomingMessageType.result.name:
            future = self._result_futures.get(message.get(MessageField.MESSAGE_ID.value, -1), None)

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
            plural_product = "_" + event.data[MessageField.SOURCE.value] + "s"
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
            self._captcha_future.set_result(event)
        if event.type == EventNameToHandler.verify_code.value:
            self._mfa_future.set_result(event)

    async def _on_open(self) -> None:
        _LOGGER.debug("on_open - executed")

    def _on_close(self) -> None:
        _LOGGER.debug("on_close - executed")

    async def _on_error(self, error: str) -> None:
        _LOGGER.error(f"on_error - {error}")
        raise WebSocketConnectionErrorException(error)

    async def _send_message_get_response(self, message: OutgoingMessage) -> dict:
        future: "asyncio.Future[dict]" = asyncio.get_event_loop().create_future()
        self._result_futures[message.id] = future
        await self.send_message(message.content)
        try:
            return await future
        finally:
            self._result_futures.pop(message.id)

    async def send_message(self, message: dict) -> None:
        """send message to websocket api"""
        _LOGGER.debug(f"send_message - {message}")
        await self._client.send_message(json.dumps(message))

    async def poll_refresh(self) -> None:
        """Poll cloud data for latest changes"""
        command_type = OutgoingMessageType.poll_refresh
        command = EventSourceType.driver.name + "." + command_type.name
        await self._send_message_get_response(OutgoingMessage(command_type, command=command))

    async def disconnect(self):
        """Disconnect the web socket and destroy it"""
        await self._client.disconnect()


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
