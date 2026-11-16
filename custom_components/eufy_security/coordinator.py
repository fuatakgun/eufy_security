"""Module to initialize coordinator"""
import asyncio
from datetime import timedelta
import json
import logging

from homeassistant.components.persistent_notification import create
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DISCONNECTED, DOMAIN
from .eufy_security_api.api_client import ApiClient
from .eufy_security_api.exceptions import (
    CaptchaRequiredException,
    DriverNotConnectedException,
    FailedCommandException,
    MultiFactorCodeRequiredException,
    WebSocketConnectionException,
)
from .model import Config

_LOGGER: logging.Logger = logging.getLogger(__package__)


class EufySecurityDataUpdateCoordinator(DataUpdateCoordinator):
    """Data update coordinator for integration"""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.config: Config = Config.parse(config_entry)
        super().__init__(hass, _LOGGER, name=DOMAIN, update_method=self._update_local, update_interval=timedelta(seconds=self.config.sync_interval))
        self._platforms = []
        self.data = {}
        self._reload_scheduled = False
        self._api = ApiClient(self.config, aiohttp_client.async_get_clientsession(self.hass), self._on_error)

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
        except (
            DriverNotConnectedException,
            WebSocketConnectionException,
            FailedCommandException,
            asyncio.TimeoutError,
        ) as exc:
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
        try:
            _LOGGER.debug(f"coordinator - start update_local")
            await self._api.poll_refresh()
            _LOGGER.debug(f"coordinator - complete update_local")
            return self.data
        except WebSocketConnectionException as exc:
            try:
                await self._api.ensure_connected()
                await self._api.sync_properties()
                return self.data
            except Exception as reconnect_exc:
                raise UpdateFailed(f"Error communicating with Add-on: {exc}") from reconnect_exc
        except (FailedCommandException, asyncio.TimeoutError) as exc:
            raise UpdateFailed(f"Error communicating with Add-on: {exc}") from exc

    async def disconnect(self):
        """disconnect from api"""
        if self._api is not None:
            await self._api.disconnect()
            self._api = None
        await self.async_shutdown()

    async def _async_reload(self, _):
        try:
            await asyncio.sleep(5)
            if self._api is None:
                return
            try:
                await self._api.ensure_connected()
                await self._api.sync_properties()
                return
            except Exception as exc:
                _LOGGER.warning(f"In-place Eufy WS reconnect failed ({exc}), scheduling reload")
            if self.config.entry.state == ConfigEntryState.LOADED:
                await self.hass.config_entries.async_reload(self.config.entry.entry_id)
        finally:
            self._reload_scheduled = False

    def _on_error(self, error):
        """Schedule background reconnect/reload when websocket closes"""
        if self._reload_scheduled:
            return
        self._reload_scheduled = True
        self.hass.bus.async_listen_once(DISCONNECTED, self._async_reload)
        self.hass.bus.async_fire(DISCONNECTED, None)

    @property
    def available(self) -> bool:
        return bool(self._api and self._api.available)

