import logging

import aiohttp
import asyncio
from datetime import timedelta
import json

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DOMAIN, PLATFORMS
from .generated import DeviceType
from .websocket import EufySecurityWebSocket

_LOGGER: logging.Logger = logging.getLogger(__package__)
START_LISTENING_MESSAGE = {"messageId": "start_listening", "command": "start_listening"}
POLL_REFRESH_MESSAGE = {"messageId": "poll_refresh", "command": "driver.poll_refresh"}
GET_PROPERTIES_METADATA_MESSAGE = {
    "messageId": "get_properties_metadata",
    "command": "{0}.get_properties_metadata",
    "serialNumber": None,
}
GET_PROPERTIES_MESSAGE = {
    "messageId": "get_properties",
    "command": None,
    "serialNumber": None,
}
SET_RTSP_STREAM = {
    "messageId": "set_rtsp_stream_on",
    "command": "device.set_rtsp_stream",
    "serialNumber": None,
    "value": None,
}

MESSAGE_IDS_TO_PROCESS = ["start_listening", "poll_refresh"]
MESSAGE_TYPES_TO_PROCESS = ["result", "event"]
PROPERTY_CHANGED_PROPERTY_NAME = "event_property_name"
EVENT_TYPE_CONFIGURATION: dict = {
    "property changed": {
        "name": PROPERTY_CHANGED_PROPERTY_NAME,
        "value": "value",
        "is_cached": False,
        "refresh_poll": False,
    },
    "person detected": {
        "name": "personDetected",
        "value": "state",
        "is_cached": False,
        "refresh_poll": True,
    },
    "motion detected": {
        "name": "motionDetected",
        "value": "state",
        "is_cached": False,
        "refresh_poll": True,
    },
    "got rtsp url": {
        "name": "rtspUrl",
        "value": "rtspUrl",
        "is_cached": True,
        "refresh_poll": False,
    },
}

DELAY_FOR_POLLING = 2


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
        self.data["data"] = {}
        self.requires_poll_callback = None
        self.initialized = False

    async def on_open(self):
        _LOGGER.debug(f"{DOMAIN} - on_open - executed")

    def set_data_value_for_property(
        self,
        sources: str,
        serial_number: str,
        property_name: str,
        value: str,
    ):
        for entity in self.data["data"][sources]:
            if entity["serialNumber"] == serial_number:
                # return entity[property_name]
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

        if self.data["cache"].get(serial_number, None) is None:
            self.data["cache"][serial_number] = {}
        self.data["cache"][serial_number][property_name] = value

    async def on_message(self, message):
        payload = message.json()
        message_type: str = payload["type"]

        if not message_type in MESSAGE_TYPES_TO_PROCESS:
            return

        message = payload[message_type]
        if message_type == "result":
            message_id: str = payload["messageId"]
            if not message_id in MESSAGE_IDS_TO_PROCESS:
                return

            if message_id == "start_listening":
                self.data["data"] = message["state"]
                self.initialized = True

            # if message_id == "poll_refresh":
            #     await self.async_start_listening()

        if message_type == "event":
            event_type = message["event"]
            event_sources = message["source"] + "s"
            event_serial_number = message["serialNumber"]
            if not event_type in EVENT_TYPE_CONFIGURATION.keys():
                return

            event_property_name = message.get(
                "name", EVENT_TYPE_CONFIGURATION[event_type]["name"]
            )
            event_property_value = message[
                EVENT_TYPE_CONFIGURATION[event_type]["value"]
            ]
            event_data_is_cached = EVENT_TYPE_CONFIGURATION[event_type]["is_cached"]
            event_requires_poll = EVENT_TYPE_CONFIGURATION[event_type]["refresh_poll"]

            if event_data_is_cached == True:
                self.set_cache_value_for_property(
                    event_sources,
                    event_serial_number,
                    event_property_name,
                    event_property_value,
                )
            else:
                self.set_data_value_for_property(
                    event_sources,
                    event_serial_number,
                    event_property_name,
                    event_property_value,
                )
            if event_requires_poll == True:
                lock = asyncio.Lock()
                _LOGGER.debug(f"{DOMAIN} - lock - {lock}")
                if lock.locked() == False:
                    _LOGGER.debug(f"{DOMAIN} - lock to acquire - {lock}")
                    await lock.acquire()
                    _LOGGER.debug(f"{DOMAIN} - fired poll refresh - {message}")
                    if not self.requires_poll_callback is None:
                        cancel_poll_callback = self.requires_poll_callback
                        cancel_poll_callback()
                    self.requires_poll_callback = async_call_later(
                        hass=self.hass,
                        delay=DELAY_FOR_POLLING,
                        action=self.async_poll_refresh,
                    )
                    lock.release()
        # self.async_start_listening()
        self.async_set_updated_data(self.data)

    async def on_close(self):
        _LOGGER.debug(f"{DOMAIN} - on_message - executed")

    async def on_error(self, message):
        _LOGGER.debug(f"{DOMAIN} - on_error - executed - {message}")

    async def initialize_ws(self):
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

    async def _async_update_data(self):
        try:
            # await self.async_start_listening()
            await self.async_poll_refresh(None)
            return self.data
        except Exception as exception:
            raise UpdateFailed() from exception

    async def async_send_message(self, message):
        await self.ws.send_message(message)

    async def async_start_listening(self):
        await self.async_send_message(json.dumps(START_LISTENING_MESSAGE))

    async def async_poll_refresh(self, executed_at):
        self.requires_poll_callback = None
        await self.async_send_message(json.dumps(POLL_REFRESH_MESSAGE))

    async def async_get_properties_metadata_for_device(
        self, device_type: DeviceType, serial_no: str
    ):
        message = GET_PROPERTIES_METADATA_MESSAGE
        message["command"] = message["command"].format(
            self.get_device_type_name(device_type)
        )
        message["serialNumber"] = serial_no
        await self.async_send_message(message)

    async def async_get_properties_for_device(
        self, device_type: DeviceType, serial_no: str
    ):
        message = GET_PROPERTIES_MESSAGE
        message["command"] = message["command"].format(
            self.get_device_type_name(device_type)
        )
        message["serialNumber"] = serial_no
        await self.async_send_message(message)

    async def async_set_rtsp(self, serial_no: str, value: bool):
        message = SET_RTSP_STREAM
        message["serialNumber"] = serial_no
        message["value"] = value
        await self.async_send_message(json.dumps(message))

    def get_device_type_name(
        self, device_type: DeviceType
    ):  # pylint: disable=no-member
        if device_type == DeviceType.STATION:
            return "station"
        return "device"
