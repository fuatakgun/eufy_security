"""Module to initialize integration"""
import asyncio
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Config, HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .const import COORDINATOR, DOMAIN, PLATFORMS
from .coordinator import EufySecurityDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup(hass: HomeAssistant, config: Config):
    """initialize the integration"""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    async def handle_send_message(call):
        coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN][COORDINATOR]
        _LOGGER.debug(f"{DOMAIN} - send_message - call.data: {call.data}")
        message = call.data.get("message")
        _LOGGER.debug(f"{DOMAIN} - end_message - message: {message}")
        await coordinator.send_message(message)

    async def handle_force_sync(call):
        coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN][COORDINATOR]
        await coordinator.async_refresh()

    async def handle_log_level(call):
        coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN][COORDINATOR]
        await coordinator.set_log_level(call.data.get("log_level"))

    hass.services.async_register(DOMAIN, "force_sync", handle_force_sync)
    hass.services.async_register(DOMAIN, "send_message", handle_send_message)
    hass.services.async_register(DOMAIN, "set_log_level", handle_log_level)

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """setup config entry"""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})

    coordinator = hass.data[DOMAIN][COORDINATOR] = hass.data[DOMAIN].get(COORDINATOR, EufySecurityDataUpdateCoordinator(hass, config_entry))

    await coordinator.initialize()
    for platform in PLATFORMS:
        coordinator.platforms.append(platform.value)
        hass.async_add_job(hass.config_entries.async_forward_entry_setup(config_entry, platform.value))

    async def update(event_time_utc):
        await coordinator.async_refresh()

    async_track_time_interval(hass, update, timedelta(seconds=coordinator.config.sync_interval))    

    config_entry.add_update_listener(async_reload_entry)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """unload active entities"""
    coordinator = hass.data[DOMAIN][COORDINATOR]
    unloaded = all(
        await asyncio.gather(
            *[hass.config_entries.async_forward_entry_unload(config_entry, platform) for platform in coordinator.platforms]
        )
    )
    if unloaded:
        await coordinator.disconnect()
        hass.data[DOMAIN] = {}

    return unloaded


async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """reload integration"""
    await async_unload_entry(hass, config_entry)
    await async_setup_entry(hass, config_entry)
