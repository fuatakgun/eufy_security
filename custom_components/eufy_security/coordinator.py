import logging

import aiohttp
import asyncio
from datetime import timedelta
import json

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.helpers.translation import component_translation_path
from .const import DEVICE_TYPE, wait_for_value

from .const import (
    DEVICE_CATEGORY,
    DOMAIN,
    PLATFORMS,
    MESSAGE_IDS_TO_PROCESS,
    MESSAGE_TYPES_TO_PROCESS,
    POLL_REFRESH_MESSAGE,
    EVENT_CONFIGURATION,
    START_LISTENING_MESSAGE,
    SET_API_SCHEMA,
    SET_RTSP_STREAM_MESSAGE,
    GET_PROPERTIES_MESSAGE,
    GET_PROPERTIES_METADATA_MESSAGE,
    GET_LIVESTREAM_STATUS_MESSAGE,
    GET_LIVESTREAM_STATUS_PLACEHOLDER,
    SET_RTSP_STREAM_MESSAGE,
    SET_LIVESTREAM_MESSAGE,
    SET_DEVICE_STATE_MESSAGE,
    SET_GUARD_MODE_MESSAGE,
    STATION_TRIGGER_ALARM,
    STATION_RESET_ALARM,
    START_LIVESTREAM_AT_INITIALIZE,
)
from .websocket import EufySecurityWebSocket

_LOGGER: logging.Logger = logging.getLogger(__package__)

DELAY_FOR_POLLING = 2
BUFFER_BASED_EVENTS = ["video_data", "audio_data"]
RETRY_COUNT = 10


class EufySecurityDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(
        self,
        hass: HomeAssistant,
        update_interval: int,
        host: str,
        port: int,
        session: aiohttp.ClientSession,
        use_rtsp_server_addon: bool = False
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )
        self.hass = hass
        self.ws = None
        self.rtsp = None
        self.host = host
        self.port = port
        self.session = session
        self.use_rtsp_server_addon = use_rtsp_server_addon
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
            self.hass,
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

        if await wait_for_value(self.__dict__, "state", {}) == True:
            return await self.get_device_properties()
        return False

    async def get_device_properties(self):
        _LOGGER.debug(f"{DOMAIN} - get_device_properties")

        if await wait_for_value(self.__dict__, "properties", {}) == False:
            return False

        for device in self.state["devices"]:
            if (await wait_for_value(self.properties, device["serialNumber"], {}) == False):
                return False
        return True

    async def on_message(self, message):
        payload = message.json()
        message_type: str = payload["type"]
        # _LOGGER.debug(f"{DOMAIN} - on_message - {payload}")
        if not message_type in MESSAGE_TYPES_TO_PROCESS:
            return
        try:
            message = payload[message_type]
        except:
            return

        if message_type == "result":
            message_id: str = payload["messageId"]
            _LOGGER.debug(f"{DOMAIN} - on_message - {payload}")
            if not message_id in MESSAGE_IDS_TO_PROCESS:
                if not GET_LIVESTREAM_STATUS_PLACEHOLDER in message_id:
                    return

            if message_id == START_LISTENING_MESSAGE["messageId"]:
                _LOGGER.debug(f"{DOMAIN} - on_message start_listening")
                self.state = message["state"]
                for device in self.state["devices"]:
                    await self.async_get_properties_for_device(device["serialNumber"])
                    await self.async_get_livestream_status(device["serialNumber"])

            if message_id == GET_PROPERTIES_MESSAGE["messageId"]:
                result = message["properties"]
                serial_number = result["serialNumber"]["value"]
                self.properties[serial_number] = result
                device_type_raw = result["type"]["value"]
                for device in self.state["devices"]:
                    if device["serialNumber"] == serial_number:
                        device["type_raw"] = device_type_raw
                        device_type = DEVICE_TYPE(device_type_raw)
                        device["type"] = str(device_type)
                        device["category"] = DEVICE_CATEGORY.get(device_type, "UNKNOWN")
                        break

            if GET_LIVESTREAM_STATUS_PLACEHOLDER in message_id:
                _LOGGER.debug(f"{DOMAIN} - GET_LIVESTREAM_STATUS_MESSAGE - {payload}")
                result = message["livestreaming"]
                serial_number = (payload["messageId"].replace(GET_LIVESTREAM_STATUS_PLACEHOLDER, "").replace(".", ""))
                if result == True:
                    for device in self.state["devices"]:
                        if device["serialNumber"] == serial_number:
                            device[START_LIVESTREAM_AT_INITIALIZE] = True
                            break

        if message_type == "event":
            event_type = message["event"]
            if not event_type in EVENT_CONFIGURATION.keys():
                return

            event_sources = message["source"] + "s"
            serial_number = message["serialNumber"]
            event_property = message.get("name", EVENT_CONFIGURATION[event_type]["name"])
            event_value = message[EVENT_CONFIGURATION[event_type]["value"]]
            event_data_type = EVENT_CONFIGURATION[event_type]["type"]

            if event_data_type == "cache":
                self.set_cache_value_for_property(event_sources, serial_number, event_property, event_value)
                if event_property in BUFFER_BASED_EVENTS:
                    self.handle_queue_data(serial_number, event_property, event_value)
                else:
                    _LOGGER.debug(f"{DOMAIN} - on_message - {payload}")
                    self.async_set_updated_data(self.data)

            if event_data_type == "state":
                self.set_data_value_for_property(event_sources, serial_number, event_property, event_value)
                _LOGGER.debug(f"{DOMAIN} - on_message - {payload}")
                self.async_set_updated_data(self.data)

            if event_data_type == "event":
                self.hass.bus.fire(f"{DOMAIN}_{serial_number}_event_received", event_value)
                video_codec = message["metadata"]["videoCodec"].lower()
                if video_codec == "unknown":
                    video_codec = "h264"
                if video_codec == "h265":
                    video_codec = "hevc"
                self.cache[serial_number]["latest_codec"] = video_codec

        else:
            self.async_set_updated_data(self.data)

    def handle_queue_data(self, serial_number, name, value):
        self.data["cache"][serial_number]["queue"].put(value)
        self.data["cache"][serial_number][name] = None

    def set_data_value_for_property(self, sources: str, serial_number: str, property_name: str, value: str):
        for entity in self.state[sources]:
            if entity["serialNumber"] == serial_number:
                entity[property_name] = value
                _LOGGER.debug(f"{DOMAIN} - set_event_for_entity - {serial_number} {property_name} {value} - {entity}")
                break

    def set_cache_value_for_property(self, sources: str, serial_number: str, property_name: str, value):
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
        await self.async_send_message(json.dumps(SET_API_SCHEMA))
        await self.async_send_message(json.dumps(START_LISTENING_MESSAGE))

    async def async_get_properties_metadata_for_device(self, serial_no: str):
        message = GET_PROPERTIES_METADATA_MESSAGE.copy()
        message["command"] = message["command"].format("device")
        message["serialNumber"] = serial_no
        await self.async_send_message(json.dumps(message))

    async def async_get_properties_for_device(self, serial_no: str):
        message = GET_PROPERTIES_MESSAGE.copy()
        message["command"] = message["command"].format("device")
        message["serialNumber"] = serial_no
        await self.async_send_message(json.dumps(message))

    async def async_get_livestream_status(self, serial_no: str):
        message = GET_LIVESTREAM_STATUS_MESSAGE.copy()
        message["serialNumber"] = serial_no
        message["messageId"] = message["messageId"].replace("{serial_no}", serial_no)
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

    async def async_set_device_state(self, serial_no: str, value: bool):
        message = SET_DEVICE_STATE_MESSAGE.copy()
        message["serialNumber"] = serial_no
        message["value"] = value
        await self.async_send_message(json.dumps(message))

    async def async_set_guard_mode(self, serial_no: str, value: int):
        message = SET_GUARD_MODE_MESSAGE.copy()
        message["serialNumber"] = serial_no
        message["mode"] = value
        await self.async_send_message(json.dumps(message))

    async def async_trigger_alarm(self, serial_no: str, duration: int = 10):
        message = STATION_TRIGGER_ALARM.copy()
        message["serialNumber"] = serial_no
        message["seconds"] = duration
        await self.async_send_message(json.dumps(message))

    async def async_reset_alarm(self, serial_no: str):
        message = STATION_RESET_ALARM.copy()
        message["serialNumber"] = serial_no
        await self.async_send_message(json.dumps(message))