import logging

import voluptuous as vol
import traceback

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import CONF_PORT, CONF_HOST, DOMAIN, PLATFORMS
from .websocket import EufySecurityWebSocket

_LOGGER = logging.getLogger(__name__)


class EufySecurityFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    def __init__(self):
        self._errors = {}

    async def async_step_user(self, user_input=None):
        self._errors = {}

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
                    vol.Required(CONF_HOST, default="192.168.178.119"): str,
                    vol.Required(CONF_PORT, default=3000): int,
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
            await eufy_ws.set_ws()
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
