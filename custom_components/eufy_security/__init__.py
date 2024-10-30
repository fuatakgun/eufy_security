"""Module to initialize integration"""
import asyncio
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.persistent_notification import create
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType
from .const import COORDINATOR, DOMAIN, PLATFORMS
from .coordinator import EufySecurityDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup(hass: HomeAssistant, config: ConfigType):
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

    coordinator = hass.data[DOMAIN][COORDINATOR] = hass.data[DOMAIN].get(
        COORDINATOR, EufySecurityDataUpdateCoordinator(hass, config_entry)
    )

    await coordinator.initialize()
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    for platform in PLATFORMS:
        coordinator.platforms.append(platform.value)

    async def update(event_time_utc):
        local_coordinator = hass.data[DOMAIN][COORDINATOR]
        await local_coordinator.async_refresh()

    config_entry.add_update_listener(async_reload_entry)
    # async_track_time_interval(hass, update, timedelta(seconds=coordinator.config.sync_interval))

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """unload active entities"""
    _LOGGER.debug(f"async_unload_entry 1")
    coordinator = hass.data[DOMAIN][COORDINATOR]
    unloaded = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)

    if unloaded:
        await coordinator.disconnect()
        hass.data[DOMAIN] = {}

    _LOGGER.debug(f"async_unload_entry 2")
    return unloaded


async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """reload integration"""
    _LOGGER.debug(f"async_reload_entry 1")
    await async_unload_entry(hass, config_entry)
    _LOGGER.debug(f"async_reload_entry 2")
    await async_setup_entry(hass, config_entry)
    _LOGGER.debug(f"async_reload_entry 3")


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    serial_no = next(iter(device_entry.identifiers))[1]
    _LOGGER.debug(f"async_remove_config_entry_device device_entry {serial_no}")
    coordinator = hass.data[DOMAIN][COORDINATOR]
    if serial_no in coordinator.devices or serial_no in coordinator.stations:
        _LOGGER.debug(f"async_remove_config_entry_device error exists {serial_no}")
        create(
            hass,
            f"Device is still accessible on account, cannot be deleted!",
            title="Eufy Security - Error",
            notification_id="eufy_security_delete_device_error",
        )
        return False
    _LOGGER.debug(f"async_remove_config_entry_device deleted {serial_no}")
    return True
