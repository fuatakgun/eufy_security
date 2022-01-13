import logging
import traceback

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .const import (
    CONF_AUTO_START_STREAM,
    CONF_CAPTCHA,
    CONF_FFMPEG_ANALYZE_DURATION,
    CONF_FIX_BINARY_SENSOR_STATE,
    CONF_HOST,
    CONF_MAP_EXTRA_ALARM_MODES,
    CONF_NAME_FOR_CUSTOM1,
    CONF_NAME_FOR_CUSTOM2,
    CONF_NAME_FOR_CUSTOM3,
    CONF_PORT,
    CONF_RTSP_SERVER_ADDRESS,
    CONF_RTSP_SERVER_PORT,
    CONF_SYNC_INTERVAL,
    CONF_USE_RTSP_SERVER_ADDON,
    COORDINATOR,
    DEFAULT_AUTO_START_STREAM,
    DEFAULT_FFMPEG_ANALYZE_DURATION,
    DEFAULT_FIX_BINARY_SENSOR_STATE,
    DEFAULT_HOST,
    DEFAULT_MAP_EXTRA_ALARM_MODES,
    DEFAULT_NAME_FOR_CUSTOM1,
    DEFAULT_NAME_FOR_CUSTOM2,
    DEFAULT_NAME_FOR_CUSTOM3,
    DEFAULT_PORT,
    DEFAULT_RTSP_SERVER_PORT,
    DEFAULT_SYNC_INTERVAL,
    DEFAULT_USE_RTSP_SERVER_ADDON,
    DOMAIN,
)
from .coordinator import EufySecurityDataUpdateCoordinator
from .websocket import EufySecurityWebSocket

_LOGGER = logging.getLogger(__name__)


class EufySecurityOptionFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry
        _LOGGER.debug(f"{DOMAIN} EufySecurityOptionFlowHandler - {config_entry.data}")
        self.schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SYNC_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SYNC_INTERVAL, DEFAULT_SYNC_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=9999)),
                vol.Optional(
                    CONF_USE_RTSP_SERVER_ADDON,
                    default=self.config_entry.options.get(
                        CONF_USE_RTSP_SERVER_ADDON, DEFAULT_USE_RTSP_SERVER_ADDON
                    ),
                ): bool,
                vol.Optional(
                    CONF_RTSP_SERVER_ADDRESS,
                    default=self.config_entry.options.get(
                        CONF_RTSP_SERVER_ADDRESS, config_entry.data.get(CONF_HOST)
                    ),
                ): str,
                vol.Optional(
                    CONF_RTSP_SERVER_PORT,
                    default=self.config_entry.options.get(
                        CONF_RTSP_SERVER_PORT, DEFAULT_RTSP_SERVER_PORT
                    ),
                ): int,
                vol.Optional(
                    CONF_FFMPEG_ANALYZE_DURATION,
                    default=self.config_entry.options.get(
                        CONF_FFMPEG_ANALYZE_DURATION, DEFAULT_FFMPEG_ANALYZE_DURATION
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=1, max=5)),
                vol.Optional(
                    CONF_AUTO_START_STREAM,
                    default=self.config_entry.options.get(
                        CONF_AUTO_START_STREAM, DEFAULT_AUTO_START_STREAM
                    ),
                ): bool,
                vol.Optional(
                    CONF_FIX_BINARY_SENSOR_STATE,
                    default=self.config_entry.options.get(
                        CONF_FIX_BINARY_SENSOR_STATE, DEFAULT_FIX_BINARY_SENSOR_STATE
                    ),
                ): bool,
                vol.Optional(
                    CONF_MAP_EXTRA_ALARM_MODES,
                    default=self.config_entry.options.get(
                        CONF_MAP_EXTRA_ALARM_MODES, DEFAULT_MAP_EXTRA_ALARM_MODES
                    ),
                ): bool,
                vol.Optional(
                    CONF_NAME_FOR_CUSTOM1,
                    default=self.config_entry.options.get(
                        CONF_NAME_FOR_CUSTOM1, DEFAULT_NAME_FOR_CUSTOM1
                    ),
                ): str,
                vol.Optional(
                    CONF_NAME_FOR_CUSTOM2,
                    default=self.config_entry.options.get(
                        CONF_NAME_FOR_CUSTOM2, DEFAULT_NAME_FOR_CUSTOM2
                    ),
                ): str,
                vol.Optional(
                    CONF_NAME_FOR_CUSTOM3,
                    default=self.config_entry.options.get(
                        CONF_NAME_FOR_CUSTOM3, DEFAULT_NAME_FOR_CUSTOM3
                    ),
                ): str,
            }
        )

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            _LOGGER.debug(f"{DOMAIN} user input in option flow : %s", user_input)
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(step_id="init", data_schema=self.schema)


class EufySecurityFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        _LOGGER.debug(f"{DOMAIN} EufySecurityOptionFlowHandler - {config_entry.data}")
        return EufySecurityOptionFlowHandler(config_entry)

    def __init__(self):
        self.coordinator: EufySecurityDataUpdateCoordinator = None
        self._errors = {}

    async def async_step_user(self, user_input=None):
        _LOGGER.debug(f"{DOMAIN} async_step_user - {user_input} - {self.__dict__}")
        self._errors = {}

        if self.source == SOURCE_REAUTH:
            self.coordinator = self.hass.data[DOMAIN][COORDINATOR]
            self.coordinator.captcha_config.set_input(user_input[CONF_CAPTCHA])
            if self._async_current_entries():
                await self.hass.config_entries.async_reload(self.context["entry_id"])

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            valid = await self._test_credentials(
                user_input[CONF_HOST], user_input[CONF_PORT]
            )
            if valid:
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )
            else:
                self._errors["base"] = "auth"

            return await self._show_config_form(user_input)

        return await self._show_config_form(user_input)

    async def _show_config_form(self, user_input):  # pylint: disable=unused-argument
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                }
            ),
            errors=self._errors,
        )

    async def _test_credentials(self, host, port):  # pylint: disable=unused-argument
        session = aiohttp_client.async_get_clientsession(self.hass)
        try:
            eufy_ws: EufySecurityWebSocket = EufySecurityWebSocket(
                None, host, port, session, None, None, None, None
            )
            await eufy_ws.connect()
            if not eufy_ws.ws.closed:
                eufy_ws.ws.close()
            return True
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error(
                f"{DOMAIN} Exception in login : %s - traceback: %s",
                ex,
                traceback.format_exc(),
            )
        return False

    async def async_step_reauth(self, user_input=None):
        _LOGGER.debug(f"{DOMAIN} async_step_reauth - {user_input}")
        self.coordinator = self.hass.data[DOMAIN][COORDINATOR]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_CAPTCHA): str,
                    }
                ),
                description_placeholders={
                    "captcha_image": '<img src="'
                    + self.coordinator.captcha_config.image
                    + '"/>'
                },
            )
        return await self.async_step_user(user_input)
