import logging

import aiohttp
import asyncio
from datetime import timedelta
from queue import Queue
import json
from homeassistant.config_entries import ConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.helpers.translation import component_translation_path
from .const import CONF_SYNC_INTERVAL, DEFAULT_SYNC_INTERVAL, DEVICE_TYPE, LATEST_CODEC, SET_LOCK_MESSAGE, EufyConfig, get_child_value, wait_for_value, Device

from .const import (
    DOMAIN,
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
    SET_LIVESTREAM_MESSAGE,
    SET_DEVICE_STATE_MESSAGE,
    SET_GUARD_MODE_MESSAGE,
    STATION_TRIGGER_ALARM,
    STATION_RESET_ALARM,
    START_LIVESTREAM_AT_INITIALIZE,
)
from .websocket import EufySecurityWebSocket

_LOGGER: logging.Logger = logging.getLogger(__package__)


class EufySecurityDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.config: EufyConfig = EufyConfig(config_entry)
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=self.config.sync_interval))
        self.ws = None
        self.session: aiohttp.ClientSession = aiohttp_client.async_get_clientsession(hass)
        self.platforms = []
        self.data = {}
        self.devices: dict = None
        self.stations: dict = None

    async def initialize_ws(self) -> bool:
        self.ws: EufySecurityWebSocket = EufySecurityWebSocket(self.hass, self.config.host, self.config.port, self.session, self.on_open, self.on_message, self.on_close, self.on_error)
        await self.ws.set_ws()
        await self.async_start_listening()
        if await self.check_if_started_listening() == False:
            _LOGGER.debug(f"{DOMAIN} - check_if_started_listening - returned False")
            raise Exception("Start Listening was not completed in timely manner")

    async def check_if_started_listening(self):
        _LOGGER.debug(f"{DOMAIN} - check_if_started_listening")

        if await wait_for_value(self.__dict__, "devices", None) == True:
            return await self.check_if_device_properties_fetched()
        return False

    async def check_if_device_properties_fetched(self):
        _LOGGER.debug(f"{DOMAIN} - get_device_properties")

        for device in self.devices.values():
            _LOGGER.debug(f"{DOMAIN} - get_device_properties - {device}")
            if await wait_for_value(device.__dict__, "properties", {}) == False:
                return False
        return True

    async def process_start_listening_response(self, states: dict):
        self.data["devices"] = {}
        self.data["stations"] = {}
        self.devices = self.data["devices"]
        self.stations = self.data["stations"]

        for state in states["devices"]:
            device = Device(state["serialNumber"], state)
            self.devices[device.serial_number] = device
            await self.async_get_properties_for_device(device.serial_number)

        for state in states["stations"]:
            device = Device(state["serialNumber"], state)
            self.stations[device.serial_number] = device

        self.devices = self.data["devices"]
        self.stations = self.data["stations"]

    async def process_get_properties_response(self, properties: dict):
        device: Device = self.devices[get_child_value(properties, "serialNumber.value")]
        device.set_properties(properties)
        if device.is_camera() == True:
            await self.async_get_livestream_status(device.serial_number)

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
            message_id = payload["messageId"]
            _LOGGER.debug(f"{DOMAIN} - on_message - {payload}")
            if not message_id in MESSAGE_IDS_TO_PROCESS:
                if not GET_LIVESTREAM_STATUS_PLACEHOLDER in message_id:
                    return

            if message_id == START_LISTENING_MESSAGE["messageId"]:
                await self.process_start_listening_response(message["state"])

            if message_id == GET_PROPERTIES_MESSAGE["messageId"]:
                await self.process_get_properties_response(message["properties"])

            if GET_LIVESTREAM_STATUS_PLACEHOLDER in message_id:
                result = message["livestreaming"]
                serial_number = (payload["messageId"].replace(GET_LIVESTREAM_STATUS_PLACEHOLDER, "").replace(".", ""))
                if result == True:
                    self.devices[serial_number].state[START_LIVESTREAM_AT_INITIALIZE] = True

        if message_type == "event":
            event_type = message["event"]
            if not event_type in EVENT_CONFIGURATION.keys():
                return

            event_source = message["source"]
            serial_number = message["serialNumber"]
            event_property = message.get("name", EVENT_CONFIGURATION[event_type]["name"])
            event_value = message[EVENT_CONFIGURATION[event_type]["value"]]
            event_data_type = EVENT_CONFIGURATION[event_type]["type"]

            if event_data_type == "state":
                _LOGGER.debug(f"{DOMAIN} - on_message - {payload}")
                self.set_value_for_property(event_source, serial_number, event_property, event_value)

            if event_data_type == "event":
                #with open("data.txt", "a") as file_object:
                    #file_object.write(json.dumps(message))
                    #file_object.write("\n")
                self.devices[serial_number].set_codec(message["metadata"]["videoCodec"].lower())
                self.hass.bus.fire(f"{DOMAIN}_{serial_number}_event_received", event_value)

    def set_value_for_property(self, source: str, serial_number: str, property_name: str, value: str):
        if isinstance(value, str):
            value = value.replace("\x00", "")
        device = None
        if source == "device":
            device: Device = self.devices[serial_number]
        if source == "station":
            device: Device = self.stations[serial_number]
        device.state[property_name] = value
        _LOGGER.debug(f"{DOMAIN} - set_event_for_entity - {source} / {serial_number} / {property_name} / {value}")

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

    async def async_set_lock(self, serial_no: str, value: bool):
        message = SET_LOCK_MESSAGE.copy()
        message["serialNumber"] = serial_no
        message["value"] = value
        await self.async_send_message(json.dumps(message))