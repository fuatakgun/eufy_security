import asyncio
import logging
import voluptuous as vol
from decimal import Decimal

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.helpers import entity_platform, service
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import make_entity_service_schema
from homeassistant.components.alarm_control_panel.const import SUPPORT_ALARM_ARM_AWAY, SUPPORT_ALARM_ARM_HOME, SUPPORT_ALARM_TRIGGER

from .const import COORDINATOR, DOMAIN, STATE_GUARD_GEO, STATE_GUARD_SCHEDULE, Device
from .entity import EufySecurityEntity
from .coordinator import EufySecurityDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)

ALARM_TRIGGER_SCHEMA = make_entity_service_schema(
    {vol.Required('duration'): cv.Number}
)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_devices):
    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN][COORDINATOR]

    entities = []
    for device in coordinator.stations.values():
        if not device.state.get("guardMode", None) is None:
            entities.append(EufySecurityAlarmControlPanel(coordinator, config_entry, device))

    async_add_devices(entities, True)
    # register entity level services
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service("alarm_guard_schedule", {}, "alarm_guard_schedule")
    platform.async_register_entity_service("alarm_arm_custom1", {}, "alarm_arm_custom1")
    platform.async_register_entity_service("alarm_arm_custom2", {}, "alarm_arm_custom2")
    platform.async_register_entity_service("alarm_arm_custom3", {}, "alarm_arm_custom3")
    platform.async_register_entity_service("alarm_guard_geo", {}, "alarm_guard_geo")
    platform.async_register_entity_service("alarm_trigger_with_duration", ALARM_TRIGGER_SCHEMA, "alarm_trigger_with_duration")
    platform.async_register_entity_service("reset_alarm", {}, "reset_alarm")



class EufySecurityAlarmControlPanel(EufySecurityEntity, AlarmControlPanelEntity):
    def __init__(self, coordinator: EufySecurityDataUpdateCoordinator, config_entry: ConfigEntry, device: Device):
        EufySecurityEntity.__init__(self, coordinator, config_entry, device)
        AlarmControlPanelEntity.__init__(self)
        self._attr_code_arm_required = False
        self._attr_supported_features = SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY | SUPPORT_ALARM_TRIGGER

    async def set_guard_mode(self, target_mode: str):
        await self.coordinator.async_set_guard_mode(self.device.serial_number, self.coordinator.get_alarm_code_from_state(target_mode))

    def alarm_disarm(self, code) -> None:
        asyncio.run_coroutine_threadsafe(self.set_guard_mode(STATE_ALARM_DISARMED), self.coordinator.hass.loop).result()

    def alarm_arm_home(self, code) -> None:
        asyncio.run_coroutine_threadsafe(self.set_guard_mode(STATE_ALARM_ARMED_HOME), self.coordinator.hass.loop).result()

    def alarm_arm_away(self, code) -> None:
        asyncio.run_coroutine_threadsafe(self.set_guard_mode(STATE_ALARM_ARMED_AWAY), self.coordinator.hass.loop).result()

    def alarm_guard_schedule(self) -> None:
        asyncio.run_coroutine_threadsafe(self.set_guard_mode(STATE_GUARD_SCHEDULE), self.coordinator.hass.loop).result()

    def alarm_arm_custom1(self) -> None:
        asyncio.run_coroutine_threadsafe(self.set_guard_mode(self.coordinator.config.alarm_custom1_name), self.coordinator.hass.loop).result()

    def alarm_arm_custom2(self) -> None:
        asyncio.run_coroutine_threadsafe(self.set_guard_mode(self.coordinator.config.alarm_custom2_name), self.coordinator.hass.loop).result()

    def alarm_arm_custom3(self) -> None:
        asyncio.run_coroutine_threadsafe(self.set_guard_mode(self.coordinator.config.alarm_custom3_name), self.coordinator.hass.loop).result()

    def alarm_guard_geo(self) -> None:
        asyncio.run_coroutine_threadsafe(self.set_guard_mode(STATE_GUARD_GEO), self.coordinator.hass.loop).result()

    def alarm_trigger(self, code) -> None:
        asyncio.run_coroutine_threadsafe(self.coordinator.async_trigger_alarm(self.device.serial_number), self.coordinator.hass.loop).result()

    def alarm_trigger_with_duration(self, duration: int = 10) -> None:
        asyncio.run_coroutine_threadsafe(self.coordinator.async_trigger_alarm(self.device.serial_number, duration), self.coordinator.hass.loop).result()

    def reset_alarm(self) -> None:
        asyncio.run_coroutine_threadsafe(self.coordinator.async_reset_alarm(self.device.serial_number), self.coordinator.hass.loop).result()

    @property
    def id(self):
        return f"{DOMAIN}_{self.device.serial_number}_station"

    @property
    def unique_id(self):
        return self.id

    @property
    def name(self):
        return self.device.name

    @property
    def state(self):
        if not self.device.state.get("alarmEvent", None) is None:
            self.device.state["alarmEvent"] = None
            return STATE_ALARM_TRIGGERED
        current_mode = self.device.state.get("currentMode")
        return self.coordinator.get_alarm_state_from_code(current_mode)