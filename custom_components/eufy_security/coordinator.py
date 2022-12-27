"""Module to initialize coordinator"""
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .eufy_security_api.api_client import ApiClient
from .eufy_security_api.exceptions import (
    CaptchaRequiredException,
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
        self.api = ApiClient(self.config.host, self.config.port, aiohttp_client.async_get_clientsession(self.hass))

    async def initialize(self):
        """Initialize the integration"""
        try:
            await self.api.connect()
        except CaptchaRequiredException as exc:
            self.config.captcha_id = exc.captcha_id
            self.config.captcha_img = exc.captcha_img
            raise ConfigEntryAuthFailed(
                "Warning: Captcha required - Go to Configurations page and enter captcha code for Eufy Security Integration"
            ) from exc
        except WebSocketConnectionError as exc:
            raise ConfigEntryNotReady() from exc

    @property
    def platforms(self):
        """Initialized platforms list"""
        return self._platforms

    @platforms.setter
    def platforms(self, value):
        self._platforms = value

    async def _update_local(self):
        # try:
        await self.api.poll_refresh()
        return self.data
        # except Exception as exception:
        # raise UpdateFailed() from exception
