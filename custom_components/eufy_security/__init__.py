import asyncio
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Config, HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .const import CAPTCHA_CONFIG, COORDINATOR, DOMAIN, PLATFORMS, CaptchaConfig
from .coordinator import EufySecurityDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup(hass: HomeAssistant, config: Config):
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    async def async_handle_send_message(call):
        coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN][COORDINATOR]
        _LOGGER.debug(f"{DOMAIN} - send_message - call.data: {call.data}")
        message = call.data.get("message")
        _LOGGER.debug(f"{DOMAIN} - end_message - message: {message}")
        await coordinator.async_send_message(message)

    async def async_force_sync(call):
        coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN][COORDINATOR]
        await coordinator.async_refresh()

    async def async_driver_connect(call):
        coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN][COORDINATOR]
        await coordinator.async_driver_connect()

    hass.services.async_register(DOMAIN, "driver_connect", async_driver_connect)
    hass.services.async_register(DOMAIN, "force_sync", async_force_sync)
    hass.services.async_register(DOMAIN, "send_message", async_handle_send_message)
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})
    captcha_config = hass.data[DOMAIN].get(CAPTCHA_CONFIG, CaptchaConfig())
    coordinator = hass.data[DOMAIN].get(
        COORDINATOR,
        EufySecurityDataUpdateCoordinator(hass, config_entry, captcha_config),
    )
    hass.data[DOMAIN][COORDINATOR] = coordinator
    hass.data[DOMAIN][CAPTCHA_CONFIG] = captcha_config

    await coordinator.initialize()
    await coordinator.async_refresh()
    for platform in PLATFORMS:
        coordinator.platforms.append(platform)
        hass.async_add_job(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    async def update(event_time_utc):
        coordinator.async_set_updated_data(coordinator.data)

    coordinator.update_listener = async_track_time_interval(
        hass, update, timedelta(seconds=1)
    )
    config_entry.add_update_listener(async_reload_entry)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    coordinator = hass.data[DOMAIN][COORDINATOR]
    unloaded = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in PLATFORMS
                if platform in coordinator.platforms
            ]
        )
    )
    coordinator.update_listener()
    if unloaded:
        hass.data[DOMAIN] = {}

    return unloaded


async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    await async_unload_entry(hass, config_entry)
    await async_setup_entry(hass, config_entry)
