"""Module to initialize coordinator"""
from datetime import timedelta
import logging
import json
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .eufy_security_api.api_client import ApiClient
from .eufy_security_api.exceptions import (
    CaptchaRequiredException,
    DriverNotConnectedError,
    MultiFactorCodeRequiredException,
    WebSocketConnectionError,
)
from .model import Config

_LOGGER: logging.Logger = logging.getLogger(__package__)


class EufySecurityDataUpdateCoordinator(DataUpdateCoordinator):
    """Data update coordinator for integration"""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.config: Config = Config.parse(config_entry)
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_method=self._update_local, update_interval=timedelta(seconds=self.config.sync_interval)
        )
        self._platforms = []
        self.data = {}
        self._api = ApiClient(self.config, aiohttp_client.async_get_clientsession(self.hass))

    async def initialize(self):
        """Initialize the integration"""
        try:
            await self._api.connect()
        except CaptchaRequiredException as exc:
            self.config.captcha_id = exc.captcha_id
            self.config.captcha_img = exc.captcha_img
            raise ConfigEntryAuthFailed() from exc
        except MultiFactorCodeRequiredException as exc:
            self.config.mfa_required = True
            raise ConfigEntryAuthFailed() from exc
        except DriverNotConnectedError as exc:
            raise ConfigEntryNotReady() from exc
        except WebSocketConnectionError as exc:
            raise ConfigEntryNotReady() from exc

    @property
    def platforms(self):
        """Initialized platforms list"""
        return self._platforms

    @property
    def devices(self) -> dict:
        """get devices from API"""
        return self._api.devices

    @property
    def stations(self) -> dict:
        """get stations from API"""
        return self._api.stations

    async def set_mfa_and_connect(self, mfa_input: str):
        """set mfa and connect"""
        await self._api.set_mfa_and_connect(mfa_input)

    async def set_captcha_and_connect(self, captcha_id: str, captcha_input: str):
        """set captcha and connect"""
        await self._api.set_captcha_and_connect(captcha_id, captcha_input)

    async def send_message(self, message: str) -> None:
        """send message to websocket api"""
        _LOGGER.debug(f"send_message - {message}")
        await self._api.send_message(message)

    async def set_log_level(self, log_level: str) -> None:
        """set log level of websocket server"""
        await self._api.set_log_level(log_level)

    async def _update_local(self):
        await self._api.poll_refresh()
        return self.data

    async def disconnect(self):
        """disconnect from api"""
        await self._api.disconnect()
