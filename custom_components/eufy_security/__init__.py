import logging

import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Config
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.aiohttp_client import async_create_clientsession


from .const import CONF_PORT, CONF_HOST, DOMAIN, PLATFORMS, DEFAULT_SYNC_INTERVAL, CONF_USE_RTSP_SERVER_ADDON
from .coordinator import EufySecurityDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup(hass: HomeAssistant, config: Config):
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    async def async_handle_send_message(call):
        coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN]
        _LOGGER.debug(f"{DOMAIN} - send_message - call.data: {call.data}")
        message = call.data["message"]
        _LOGGER.debug(f"{DOMAIN} - end_message - message: {message}")
        await coordinator.async_send_message(message)

    hass.services.async_register(DOMAIN, "send_message", async_handle_send_message)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})

    host = entry.data.get(CONF_HOST)
    port = entry.data.get(CONF_PORT)
    session = aiohttp_client.async_get_clientsession(hass)
    use_rtsp_server_addon = entry.options.get(CONF_USE_RTSP_SERVER_ADDON, False)
    coordinator: EufySecurityDataUpdateCoordinator = EufySecurityDataUpdateCoordinator(hass, DEFAULT_SYNC_INTERVAL, host, port, session, use_rtsp_server_addon)

    await coordinator.initialize_ws()
    await coordinator.async_refresh()

    hass.data[DOMAIN] = coordinator
    for platform in PLATFORMS:
        coordinator.platforms.append(platform)
        hass.async_add_job(hass.config_entries.async_forward_entry_setup(entry, platform))

    entry.add_update_listener(async_reload_entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = hass.data[DOMAIN]
    unloaded = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
                if platform in coordinator.platforms
            ]
        )
    )
    if unloaded:
        hass.data[DOMAIN] = []

    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
