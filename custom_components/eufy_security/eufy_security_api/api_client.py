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
    EventSourceType,
    MessageField,
    ProductCommand,
    ProductType,
)
from .event import Event
from .exceptions import (
    CaptchaRequiredException,
    DeviceNotInitializedYetException,
    DriverNotConnectedException,
    FailedCommandException,
    IncompatibleVersionException,
    MultiFactorCodeRequiredException,
    UnexpectedMessageTypeException,
    UnknownEventSourceException,
    WebSocketConnectionException,
)
from .outgoing_message import OutgoingMessage, OutgoingMessageType
from .product import Device, Product, Station
from .web_socket_client import WebSocketClient


class ApiClient:
    """Client to communicate with eufy-security-ws over websocket connection"""

    def __init__(self, config, session: aiohttp.ClientSession, on_error_callback) -> None:
        self._config = config
        self._client: WebSocketClient = WebSocketClient(self._config.host, self._config.port, session, self._on_open, self._on_message, self._on_close, self._on_error)
        self._on_error_callback = on_error_callback
        self._result_futures: dict[str, asyncio.Future] = {}
        self._devices: dict = None
        self._stations: dict = None
        self._captcha_future: asyncio.Future[dict] = asyncio.get_event_loop().create_future()
        self._mfa_future: asyncio.Future[dict] = asyncio.get_event_loop().create_future()

    @property
    def devices(self) -> dict:
        """initialized devices"""
        return self._devices

    @property
    def stations(self) -> dict:
        """initialized stations"""
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
            _LOGGER.debug(f"_check_interactive_mode 1")
            await asyncio.wait_for(self._captcha_future, timeout=10)
            event = self._captcha_future.result()
            raise CaptchaRequiredException(event.data[MessageField.CAPTCHA_ID.value], event.data[MessageField.CAPTCHA_IMG.value])
        except (asyncio.exceptions.TimeoutError, asyncio.exceptions.CancelledError):
            pass
        _LOGGER.debug(f"_check_interactive_mode 2")
        # driver is not connected and captcha exception is not thrown, wait for mfa event
        try:
            _LOGGER.debug(f"_check_interactive_mode 3")
            await asyncio.wait_for(self._mfa_future, timeout=5)
            event = self._mfa_future.result()
            raise MultiFactorCodeRequiredException()
        except (asyncio.exceptions.TimeoutError, asyncio.exceptions.CancelledError) as exc:
            _LOGGER.debug(f"_check_interactive_mode 4")
            await self._connect_driver()
            raise DriverNotConnectedException() from exc

    async def _set_products(self) -> None:
        _LOGGER.debug(f"_set_products 1")
        self._captcha_future = asyncio.get_event_loop().create_future()
        self._mfa_future = asyncio.get_event_loop().create_future()
        result = await self._start_listening()
        _LOGGER.debug(f"_set_products 2")

        if result[MessageField.STATE.value][EventSourceType.driver.name][MessageField.CONNECTED.value] is False:
            await self._check_interactive_mode()

        self._devices = await self._get_products(ProductType.device, result[MessageField.STATE.value]["devices"])
        self._stations = await self._get_products(ProductType.station, result[MessageField.STATE.value]["stations"])

    async def _get_products(self, product_type: ProductType, products: list) -> dict:
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
                    product = Camera(self, serial_no, properties, metadata, commands, self._config, is_rtsp_streaming, is_p2p_streaming, voices)
                else:
                    product = Device(self, serial_no, properties, metadata, commands)
            else:
                properties[MessageField.CONNECTED.value] = await self._get_is_connected(product_type, serial_no)
                metadata[MessageField.CONNECTED.value] = {'key': MessageField.CONNECTED.value,'name': MessageField.CONNECTED.value,'label': 'Connected','readable': True,'writeable': False,'type': 'boolean'}
                product = Station(self, serial_no, properties, metadata, commands)

            response[serial_no] = product
        return response

    async def set_captcha_and_connect(self, captcha_id: str, captcha_input: str):
        """Set captcha set products"""
        await self._set_captcha(captcha_id, captcha_input)
        await asyncio.sleep(30)
        # await self._set_products()

    async def set_mfa_and_connect(self, mfa_input: str):
        """Set mfa code set products"""
        await self._set_mfa_code(mfa_input)
        await asyncio.sleep(30)
        # await self._set_products()

    # server level commands
    async def _start_listening(self):
        return await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.start_listening))

    async def _set_schema(self, schema_version: int) -> None:
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.set_api_schema, schema_version=schema_version))

    # driver level commands
    async def _disconnect_driver(self) -> None:
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.disconnect))

    async def _connect_driver(self) -> None:
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.connect))

    async def set_log_level(self, log_level: str) -> None:
        """set log level of websocket server"""
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.set_log_level, log_level=log_level))

    async def poll_refresh(self) -> None:
        """Poll cloud data for latest changes"""
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.poll_refresh))

    async def _set_captcha(self, captcha_id: str, captcha_input: str) -> None:
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.set_captcha, captcha_id=captcha_id, captcha_input=captcha_input))

    async def _set_mfa_code(self, mfa_input: str) -> None:
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.set_verify_code, verify_code=mfa_input))

    # product (both device and station) level commands
    async def _get_metadata(self, product_type: ProductType, serial_no: str) -> dict:
        result = await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.get_properties_metadata, domain=product_type.name, serial_no=serial_no))
        return result[MessageField.PROPERTIES.value]

    async def _get_properties(self, product_type: ProductType, serial_no: str) -> dict:
        result = await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.get_properties, domain=product_type.name, serial_no=serial_no))
        return result[MessageField.PROPERTIES.value]

    async def _get_commands(self, product_type: ProductType, serial_no: str) -> dict:
        result = await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.get_commands, domain=product_type.name, serial_no=serial_no))
        return result[MessageField.COMMANDS.value]

    async def set_property(self, product_type: ProductType, serial_no: str, name: str, value: Any) -> None:
        """Process set property call"""
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.set_property, domain=product_type.name, serial_no=serial_no, name=name, value=value))

    async def trigger_alarm(self, product_type: ProductType, serial_no: str, duration: int) -> None:
        """Process trigger alarm call"""
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.trigger_alarm, domain=product_type.name, serial_no=serial_no, seconds=duration))

    async def reset_alarm(self, product_type: ProductType, serial_no: str) -> None:
        """Process reset alarm call"""
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.reset_alarm, domain=product_type.name, serial_no=serial_no))

    # device level commands
    async def pan_and_tilt(self, product_type: ProductType, serial_no: str, direction: int) -> None:
        """Process start pan tilt rotate zoom"""
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.pan_and_tilt, serial_no=serial_no, direction=direction))

    async def preset_position(self, product_type: ProductType, serial_no: str, position: int) -> None:
        """Process preset position call"""
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.preset_position, serial_no=serial_no, position=position))

    async def save_preset_position(self, product_type: ProductType, serial_no: str, position: int) -> None:
        """Process save preset position call"""
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.save_preset_position, serial_no=serial_no, position=position))

    async def delete_preset_position(self, product_type: ProductType, serial_no: str, position: int) -> None:
        """Process delete preset position call"""
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.delete_preset_position, serial_no=serial_no, position=position))

    async def start_rtsp_livestream(self, product_type: ProductType, serial_no: str) -> None:
        """Process start rtsp livestream call"""
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.start_rtsp_livestream, serial_no=serial_no))

    async def calibrate(self, product_type: ProductType, serial_no: str) -> None:
        """Process calibrate camera call"""
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.calibrate, serial_no=serial_no))

    async def stop_rtsp_livestream(self, product_type: ProductType, serial_no: str) -> None:
        """Process stop rtsp livestream call"""
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.stop_rtsp_livestream, serial_no=serial_no))

    async def _get_is_rtsp_streaming(self, product_type: ProductType, serial_no: str) -> bool:
        result = await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.is_rtsp_livestreaming, serial_no=serial_no))
        return result[MessageField.LIVE_STREAMING.value]

    async def _get_is_connected(self, product_type: ProductType, serial_no: str) -> bool:
        result = await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.is_connected, serial_no=serial_no))
        return result[MessageField.CONNECTED.value]

    async def start_livestream(self, product_type: ProductType, serial_no: str) -> None:
        """Process start p2p livestream call"""
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.start_livestream, serial_no=serial_no))

    async def stop_livestream(self, product_type: ProductType, serial_no: str) -> None:
        """Process stop p2p livestream call"""
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.stop_livestream, serial_no=serial_no))

    async def _get_is_p2p_streaming(self, product_type: ProductType, serial_no: str) -> bool:
        result = await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.is_livestreaming, serial_no=serial_no))
        return result[MessageField.LIVE_STREAMING.value]

    async def _get_voices(self, product_type: ProductType, serial_no: str) -> dict:
        result = await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.get_voices, domain=product_type.name, serial_no=serial_no))
        return result[MessageField.VOICES.value]

    async def quick_response(self, product_type: ProductType, serial_no: str, voice_id: int) -> None:
        """Process quick response for doorbell"""
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.quick_response, serial_no=serial_no, voice_id=voice_id))

    async def snooze(self, product_type: ProductType, serial_no: str, snooze_time: int, snooze_chime: bool, snooze_motion: bool, snooze_homebase: bool) -> None:
        """Process snooze for devices ans stations"""
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.snooze, serial_no=serial_no, snooze_time=snooze_time, snooze_chime=snooze_chime, snooze_motion=snooze_motion, snooze_homebase=snooze_homebase))

    async def verify_pin(self, product_type: ProductType, serial_no: str, pin: str) -> None:
        """verify pin for safe product"""
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.verify_pin, serial_no=serial_no, pin=pin))

    async def unlock(self, product_type: ProductType, serial_no: str) -> None:
        """unlock for safe product"""
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.unlock, serial_no=serial_no))

    # station level commands

    async def chime(self, product_type: ProductType, serial_no: str, ringtone: int) -> None:
        """Process chme call"""
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.chime, serial_no=serial_no, ringtone=ringtone))

    async def reboot(self, product_type: ProductType, serial_no: str) -> None:
        """Process reboot call"""
        await self._send_message_get_response(OutgoingMessage(OutgoingMessageType.reboot, serial_no=serial_no))

    async def _on_message(self, message: dict) -> None:
        message_str = str(message)[0:15000]
        if "livestream video data" not in message_str and "livestream audio data" not in message_str:
            _LOGGER.debug(f"_on_message - {message_str}")
        else:
            # _LOGGER.debug(f"_on_message - livestream data received - {len(str(message))}")
            pass
        if message[MessageField.TYPE.value] == IncomingMessageType.result.name:
            future = self._result_futures.get(message.get(MessageField.MESSAGE_ID.value, -1), None)

            if future is None:
                return

            if message[MessageField.SUCCESS.value]:
                future.set_result(message[IncomingMessageType.result.name])
                return

            future.set_exception(FailedCommandException(message[MessageField.MESSAGE_ID.value], message[MessageField.ERROR_CODE.value], message))
        elif message[MessageField.TYPE.value] == IncomingMessageType.event.name:
            event: Event = Event(type=message[IncomingMessageType.event.name][IncomingMessageType.event.name], data=message[IncomingMessageType.event.name])
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
                product = self.__dict__[plural_product][event.data[MessageField.SERIAL_NO.value]]
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

    def _on_close(self, future="") -> None:
        _LOGGER.debug(f"on_close - executed - {future} = {future.exception()}")
        if self._on_error_callback is not None:
            self._on_error_callback(future)
        if future.exception() is not None:
            _LOGGER.debug(f"on_close - executed - {future.exception()}")
            raise future.exception()

    async def _on_error(self, error: str) -> None:
        _LOGGER.error(f"on_error - {error}")
        raise WebSocketConnectionException(error)

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

    async def disconnect(self):
        """Disconnect the web socket and destroy it"""
        self._on_error_callback = None
        await self._client.disconnect()
        self._client = None

    @property
    def available(self) -> bool:
        return self._client.available




class IncomingMessageType(Enum):
    """Incoming message types"""

    version = "version"
    result = "result"
    event = "event"
