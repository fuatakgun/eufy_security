import logging

import aiohttp
import asyncio
from datetime import timedelta
import json

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import (
    DOMAIN,
    PLATFORMS,
    MESSAGE_IDS_TO_PROCESS,
    MESSAGE_TYPES_TO_PROCESS,
    POLL_REFRESH_MESSAGE,
    EVENT_CONFIGURATION,
    START_LISTENING_MESSAGE,
    SET_RTSP_STREAM_MESSAGE,
    GET_PROPERTIES_MESSAGE,
    GET_PROPERTIES_METADATA_MESSAGE,
    SET_RTSP_STREAM_MESSAGE,
    SET_LIVESTREAM_MESSAGE,
)
from .generated import DeviceType
from .websocket import EufySecurityWebSocket

_LOGGER: logging.Logger = logging.getLogger(__package__)

DELAY_FOR_POLLING = 2
BUFFER_BASED_EVENTS = ["video_data", "audio_data"]


class EufySecurityDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        update_interval: int,
        host: str,
        port: int,
        session: aiohttp.ClientSession,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )
        self.ws = None
        self.host = host
        self.port = port
        self.session = session
        self.platforms = []
        self.data = {}
        self.data["cache"] = {}
        self.cache = self.data["cache"]
        self.data["state"] = {}
        self.state = self.data["state"]
        self.data["properties"] = {}
        self.properties = self.data["properties"]

    async def initialize_ws(self) -> bool:
        self.ws: EufySecurityWebSocket = EufySecurityWebSocket(
            self.host,
            self.port,
            self.session,
            self.on_open,
            self.on_message,
            self.on_close,
            self.on_error,
        )
        await self.ws.set_ws()
        await self.async_start_listening()
        if await self.check_if_started_listening() == False:
            _LOGGER.debug(f"{DOMAIN} - check_if_started_listening - returned False")
            raise Exception("Start Listening was not completed in timely manner")

    async def check_if_started_listening(self):
        _LOGGER.debug(f"{DOMAIN} - check_if_started_listening")
        for counter in range(0, 5):
            if self.state.get("devices", None) is None:
                _LOGGER.debug(f"{DOMAIN} - check_if_started_listening - {counter}")
                await asyncio.sleep(1)
            else:
                return await self.get_device_properties()
        return False

    async def get_device_properties(self):
        _LOGGER.debug(f"{DOMAIN} - get_device_properties")
        for counter in range(0, 5):
            missing_exist = False
            for device in self.state["devices"]:
                serial_number = device["serialNumber"]
                if self.properties.get(serial_number, None) is None:
                    _LOGGER.debug(
                        f"{DOMAIN} - device missing - {serial_number} - {counter}"
                    )
                    missing_exist = True
            if missing_exist == True:
                await asyncio.sleep(1)
            else:
                return True
        return False

    async def on_message(self, message):
        payload = message.json()
        message_type: str = payload["type"]
        _LOGGER.debug(f"{DOMAIN} - on_message message_type - {message_type}")
        if not message_type in MESSAGE_TYPES_TO_PROCESS:
            return
        try:
            message = payload[message_type]
        except:
            return

        if message_type == "result":
            message_id: str = payload["messageId"]
            _LOGGER.debug(f"{DOMAIN} - on_message result message_id - {message_id}")
            if not message_id in MESSAGE_IDS_TO_PROCESS:
                return

            if message_id == START_LISTENING_MESSAGE["messageId"]:
                _LOGGER.debug(f"{DOMAIN} - on_message start_listening")
                self.state = message["state"]
                for device in self.state["devices"]:
                    await self.async_get_properties_for_device(device["serialNumber"])

            if message_id == GET_PROPERTIES_MESSAGE["messageId"]:
                result = message["properties"]
                serial_number = result["serialNumber"]["value"]
                self.properties[serial_number] = result

        if message_type == "event":
            event_type = message["event"]
            event_sources = message["source"] + "s"
            serial_number = message["serialNumber"]
            if not event_type in EVENT_CONFIGURATION.keys():
                return

            event_property = message.get(
                "name", EVENT_CONFIGURATION[event_type]["name"]
            )
            event_value = message[EVENT_CONFIGURATION[event_type]["value"]]
            event_data_is_cached = EVENT_CONFIGURATION[event_type]["is_cached"]

            if event_data_is_cached == True:
                self.set_cache_value_for_property(
                    event_sources,
                    serial_number,
                    event_property,
                    event_value,
                )
                if event_property in BUFFER_BASED_EVENTS:
                    self.handle_queue_data(
                        serial_number, event_property, event_value, message
                    )
                else:
                    self.async_set_updated_data(self.data)
            else:
                self.set_data_value_for_property(
                    event_sources, serial_number, event_property, event_value
                )
                self.async_set_updated_data(self.data)
        else:
            self.async_set_updated_data(self.data)

    def handle_queue_data(self, serial_number, name, value, message):
        self.data["cache"][serial_number]["video_codec"] = message["metadata"][
            "videoCodec"
        ].lower()
        self.data["cache"][serial_number]["queue"].append(value)
        self.data["cache"][serial_number][name] = None

    def set_data_value_for_property(
        self,
        sources: str,
        serial_number: str,
        property_name: str,
        value: str,
    ):
        for entity in self.state[sources]:
            if entity["serialNumber"] == serial_number:
                entity[property_name] = value
                _LOGGER.debug(
                    f"{DOMAIN} - set_event_for_entity -{serial_number} {property_name} {value}"
                )
                break

    def set_cache_value_for_property(
        self,
        sources: str,
        serial_number: str,
        property_name: str,
        value,
    ):
        if isinstance(value, str):
            value = value.replace("\x00", "")

        self.data["cache"][serial_number][property_name] = value

    async def on_open(self):
        _LOGGER.debug(f"{DOMAIN} - on_open - executed")

    async def on_close(self):
        _LOGGER.debug(f"{DOMAIN} - on_close - executed")

    async def on_error(self, message):
        _LOGGER.debug(f"{DOMAIN} - on_error - executed - {message}")

    async def _async_update_data(self):
        try:
            await self.async_send_message(json.dumps(POLL_REFRESH_MESSAGE))
            return self.data
        except Exception as exception:
            raise UpdateFailed() from exception

    async def async_send_message(self, message):
        if self.ws.ws is None or self.ws.ws.closed == True:
            await self.initialize_ws()
        await self.ws.send_message(message)

    async def async_start_listening(self):
        await self.async_send_message(json.dumps(START_LISTENING_MESSAGE))

    async def async_get_properties_metadata_for_device(
        self, device_type: DeviceType, serial_no: str
    ):
        message = GET_PROPERTIES_METADATA_MESSAGE.copy()
        message["command"] = message["command"].format("device")
        message["serialNumber"] = serial_no
        await self.async_send_message(json.dumps(message))

    async def async_get_properties_for_device(self, serial_no: str):
        message = GET_PROPERTIES_MESSAGE.copy()
        message["command"] = message["command"].format("device")
        message["serialNumber"] = serial_no
        await self.async_send_message(json.dumps(message))

    async def async_set_rtsp(self, serial_no: str, value: bool):
        message = SET_RTSP_STREAM_MESSAGE.copy()
        message["serialNumber"] = serial_no
        message["value"] = value
        await self.async_send_message(json.dumps(message))

    async def async_set_livestream(self, serial_no: str, value: str):
        message = SET_LIVESTREAM_MESSAGE.copy()
        message["serialNumber"] = serial_no
        message["command"] = message["command"].replace("{state}", value)
        await self.async_send_message(json.dumps(message))
