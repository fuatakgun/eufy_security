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
)
from homeassistant.helpers import entity_platform, service
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import make_entity_service_schema
from homeassistant.components.alarm_control_panel.const import SUPPORT_ALARM_ARM_AWAY, SUPPORT_ALARM_ARM_HOME, SUPPORT_ALARM_TRIGGER

from .const import DOMAIN, STATE_ALARM_CUSTOM1, STATE_ALARM_CUSTOM2, STATE_ALARM_CUSTOM3, STATE_GUARD_GEO, STATE_GUARD_SCHEDULE
from .entity import EufySecurityEntity
from .coordinator import EufySecurityDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)

CODES_TO_STATES = {
    0: STATE_ALARM_ARMED_AWAY,
    1: STATE_ALARM_ARMED_HOME,
    2: STATE_GUARD_SCHEDULE,
    3: STATE_ALARM_CUSTOM1,
    4: STATE_ALARM_CUSTOM2,
    5: STATE_ALARM_CUSTOM3,
    47: STATE_GUARD_GEO,
    63: STATE_ALARM_DISARMED
}

ALARM_TRIGGER_SCHEMA = make_entity_service_schema(
    {vol.Required('duration'): cv.Number}
)


async def async_setup_entry(hass, entry, async_add_devices):
    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN]

    entities = []
    for entity in coordinator.state["stations"]:
        if not entity.get("guardMode", None) is None:
            entities.append(EufySecurityAlarmControlPanel(hass, coordinator, entry, entity))

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
    def __init__(self, hass: HomeAssistant, coordinator: EufySecurityDataUpdateCoordinator, entry: ConfigEntry, entity: dict):
        EufySecurityEntity.__init__(self, coordinator, entry, entity)
        AlarmControlPanelEntity.__init__(self)
        self._attr_code_arm_required = False
        self._attr_supported_features = SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY | SUPPORT_ALARM_TRIGGER

        self.hass: HomeAssistant = hass
        self.coordinator: EufySecurityDataUpdateCoordinator = coordinator
        self.entity = entity
        self.states_to_codes = {v: k for k, v in CODES_TO_STATES.items()}

        # initialize values
        self.serial_number = self.entity["serialNumber"]

    async def set_guard_mode(self, target_mode: str):
        await self.coordinator.async_set_guard_mode(self.serial_number, self.states_to_codes[target_mode])

    def alarm_disarm(self, code) -> None:
        asyncio.run_coroutine_threadsafe(self.set_guard_mode(STATE_ALARM_DISARMED), self.hass.loop).result()

    def alarm_arm_home(self, code) -> None:
        asyncio.run_coroutine_threadsafe(self.set_guard_mode(STATE_ALARM_ARMED_HOME), self.hass.loop).result()

    def alarm_arm_away(self, code) -> None:
        asyncio.run_coroutine_threadsafe(self.set_guard_mode(STATE_ALARM_ARMED_AWAY), self.hass.loop).result()

    def alarm_guard_schedule(self) -> None:
        asyncio.run_coroutine_threadsafe(self.set_guard_mode(STATE_GUARD_SCHEDULE), self.hass.loop).result()

    def alarm_arm_custom1(self) -> None:
        asyncio.run_coroutine_threadsafe(self.set_guard_mode(STATE_ALARM_CUSTOM1), self.hass.loop).result()

    def alarm_arm_custom2(self) -> None:
        asyncio.run_coroutine_threadsafe(self.set_guard_mode(STATE_ALARM_CUSTOM2), self.hass.loop).result()

    def alarm_arm_custom3(self) -> None:
        asyncio.run_coroutine_threadsafe(self.set_guard_mode(STATE_ALARM_CUSTOM3), self.hass.loop).result()

    def alarm_guard_geo(self) -> None:
        asyncio.run_coroutine_threadsafe(self.set_guard_mode(STATE_GUARD_GEO), self.hass.loop).result()

    def alarm_trigger(self, code) -> None:
        asyncio.run_coroutine_threadsafe(self.coordinator.async_trigger_alarm(self.serial_number), self.hass.loop).result()

    def alarm_trigger_with_duration(self, duration: int = 10) -> None:
        asyncio.run_coroutine_threadsafe(self.coordinator.async_trigger_alarm(self.serial_number, duration), self.hass.loop).result()

    def reset_alarm(self) -> None:
        asyncio.run_coroutine_threadsafe(self.coordinator.async_reset_alarm(self.serial_number), self.hass.loop).result()

    @property
    def id(self):
        return f"{DOMAIN}_{self.serial_number}_station"

    @property
    def unique_id(self):
        return self.id

    @property
    def name(self):
        return self.entity.get("name", "Missing Name")

    @property
    def state(self):
        current_mode = self.entity.get("currentMode", -1)
        return CODES_TO_STATES[current_mode]

    @property
    def state_attributes(self):
        attrs = {}
        attrs["data"] = self.entity
        attrs["guard_state"] = CODES_TO_STATES[self.entity.get("guardMode", -1)]
        return attrs