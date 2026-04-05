"""Module to initialize integration"""
from __future__ import annotations

import logging
from typing import TypeAlias

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.persistent_notification import create
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.typing import ConfigType
from .const import DOMAIN, PLATFORMS
from .coordinator import EufySecurityDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)

EufySecurityConfigEntry: TypeAlias = ConfigEntry[EufySecurityDataUpdateCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType):
    """initialize the integration"""

    async def handle_send_message(call):
        for entry in hass.config_entries.async_entries(DOMAIN):
            if hasattr(entry, "runtime_data") and entry.runtime_data:
                await entry.runtime_data.send_message(call.data.get("message"))
                return

    async def handle_force_sync(call):
        for entry in hass.config_entries.async_entries(DOMAIN):
            if hasattr(entry, "runtime_data") and entry.runtime_data:
                await entry.runtime_data.async_refresh()
                return

    async def handle_log_level(call):
        for entry in hass.config_entries.async_entries(DOMAIN):
            if hasattr(entry, "runtime_data") and entry.runtime_data:
                await entry.runtime_data.set_log_level(call.data.get("log_level"))
                return

    hass.services.async_register(DOMAIN, "force_sync", handle_force_sync)
    hass.services.async_register(DOMAIN, "send_message", handle_send_message)
    hass.services.async_register(DOMAIN, "set_log_level", handle_log_level)

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: EufySecurityConfigEntry):
    """setup config entry"""
    coordinator = EufySecurityDataUpdateCoordinator(hass, config_entry)
    config_entry.runtime_data = coordinator

    await coordinator.initialize()
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    for platform in PLATFORMS:
        coordinator.platforms.append(platform.value)

    config_entry.add_update_listener(async_reload_entry)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: EufySecurityConfigEntry) -> bool:
    """unload active entities"""
    coordinator = config_entry.runtime_data
    unloaded = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)

    if unloaded:
        await coordinator.disconnect()

    return unloaded


async def async_reload_entry(hass: HomeAssistant, config_entry: EufySecurityConfigEntry) -> None:
    """reload integration"""
    await async_unload_entry(hass, config_entry)
    await async_setup_entry(hass, config_entry)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: EufySecurityConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    serial_no = next(iter(device_entry.identifiers))[1]
    _LOGGER.debug("async_remove_config_entry_device device_entry %s", serial_no)
    coordinator = config_entry.runtime_data
    if serial_no in coordinator.devices or serial_no in coordinator.stations:
        _LOGGER.debug("async_remove_config_entry_device error exists %s", serial_no)
        create(
            hass,
            "Device is still accessible on account, cannot be deleted!",
            title="Eufy Security - Error",
            notification_id="eufy_security_delete_device_error",
        )
        return False
    _LOGGER.debug("async_remove_config_entry_device deleted %s", serial_no)
    return True
