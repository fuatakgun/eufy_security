from __future__ import annotations

from enum import Enum, auto
import logging

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import COORDINATOR, DOMAIN, Schema
from .coordinator import EufySecurityDataUpdateCoordinator
from .entity import EufySecurityEntity
from .eufy_security_api.const import MessageField
from .eufy_security_api.metadata import Metadata
from .eufy_security_api.util import get_child_value

_LOGGER: logging.Logger = logging.getLogger(__package__)

#KEYPAD_OFF_CODE = 6


class CurrentModeToState(Enum):
    """Alarm Entity Mode to State"""

    NONE = -1
    AWAY = 0
    HOME = 1
    SCHEDULE = 2
    CUSTOM_BYPASS = 3
    NIGHT = 4
    VACATION = 5
    OFF = 6
    GEOFENCE = 47
    DISARMED = 63

class CurrentModeToStateValue(Enum):
    """Alarm Entity Mode to State Value"""

    NONE = "Unknown"
    AWAY = AlarmControlPanelState.ARMED_AWAY
    HOME = AlarmControlPanelState.ARMED_HOME
    CUSTOM_BYPASS = 3
    NIGHT = 4
    VACATION = 5
    DISARMED = AlarmControlPanelState.DISARMED
    OFF = STATE_OFF
    TRIGGERED = AlarmControlPanelState.TRIGGERED
    ALARM_DELAYED = "Alarm delayed"


CUSTOM_CODES = [3, 4, 5]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Setup alarm control panel entities."""
    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN][COORDINATOR]
    product_properties = []
    for product in coordinator.stations.values():
        if product.has(MessageField.GUARD_MODE.value) is True:
            product_properties.append(product.metadata[MessageField.CURRENT_MODE.value])

    entities = [EufySecurityAlarmControlPanel(coordinator, metadata) for metadata in product_properties]
    async_add_entities(entities)
    # register entity level services
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "trigger_base_alarm_with_duration", Schema.TRIGGER_ALARM_SERVICE_SCHEMA.value, "async_alarm_trigger_with_duration"
    )
    platform.async_register_entity_service("reset_alarm", {}, "async_reset_alarm")
    platform.async_register_entity_service("alarm_arm_custom1", {}, "async_alarm_arm_custom_bypass")
    platform.async_register_entity_service("alarm_arm_custom2", {}, "async_alarm_arm_night")
    platform.async_register_entity_service("alarm_arm_custom3", {}, "async_alarm_arm_vacation")
    platform.async_register_entity_service("geofence", {}, "geofence")
    platform.async_register_entity_service("schedule", {}, "schedule")
    platform.async_register_entity_service("chime", Schema.CHIME_SERVICE_SCHEMA.value, "chime")
    platform.async_register_entity_service("reboot", {}, "reboot")
    platform.async_register_entity_service("alarm_off", {}, "async_alarm_off")



class EufySecurityAlarmControlPanel(AlarmControlPanelEntity, EufySecurityEntity):
    """Base alarm control panel entity for integration"""

    def __init__(self, coordinator: EufySecurityDataUpdateCoordinator, metadata: Metadata) -> None:
        super().__init__(coordinator, metadata)
        self._attr_name = f"{self.product.name}"
        self._attr_icon = None
        self._attr_code_arm_required = False
        self._attr_supported_features = (
            AlarmControlPanelEntityFeature.ARM_HOME
            | AlarmControlPanelEntityFeature.ARM_AWAY
            | AlarmControlPanelEntityFeature.TRIGGER
            | AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS
            | AlarmControlPanelEntityFeature.ARM_NIGHT
            | AlarmControlPanelEntityFeature.ARM_VACATION

        )

    @property
    def guard_mode_metadata(self) -> Metadata:
        """Get guard mode metadata for device"""
        return self.product.metadata[MessageField.GUARD_MODE.value]

    @property
    def guard_mode(self) -> Metadata:
        """Get guard mode for device"""
        return get_child_value(self.product.properties, MessageField.GUARD_MODE.value)

    async def _set_guard_mode(self, target_mode: CurrentModeToState):
        await self.product.set_property(self.guard_mode_metadata, target_mode.value)

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        await self._set_guard_mode(CurrentModeToState.DISARMED)

    async def async_alarm_off(self, code: str | None = None) -> None:
        await self._set_guard_mode(CurrentModeToState.OFF)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        await self._set_guard_mode(CurrentModeToState.HOME)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        await self._set_guard_mode(CurrentModeToState.AWAY)

    async def async_alarm_arm_custom_bypass(self, code: str | None = None) -> None:
        await self._set_guard_mode(CurrentModeToState.CUSTOM_BYPASS)

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        await self._set_guard_mode(CurrentModeToState.NIGHT)

    async def async_alarm_arm_vacation(self, code: str | None = None) -> None:
        await self._set_guard_mode(CurrentModeToState.VACATION)

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """trigger alarm for a duration on alarm control panel but there is no change in current mode"""
        await self.product.trigger_alarm()

    async def async_alarm_trigger_with_duration(self, duration: int = 10) -> None:
        """trigger alarm for a duration on alarm control panel but there is no change in current mode"""
        await self.product.trigger_alarm(duration)

    async def async_reset_alarm(self) -> None:
        """reset ongoing alarm but there is no change in current mode"""
        await self.product.reset_alarm()

    async def geofence(self) -> None:
        """switch to geofence mode"""
        await self._set_guard_mode(CurrentModeToState.GEOFENCE)

    async def schedule(self) -> None:
        """switch to schedule mode"""
        await self._set_guard_mode(CurrentModeToState.SCHEDULE)

    async def chime(self, ringtone: int) -> None:
        """chime on alarm control panel"""
        await self.product.chime(ringtone)

    async def reboot(self) -> None:
        """reboot"""
        await self.product.reboot()

    @property
    def alarm_state(self):
        alarm_delayed = get_child_value(self.product.properties, "alarmDelay", 0)
        if alarm_delayed > 0:
            return CurrentModeToStateValue.ALARM_DELAYED.value

        triggered = get_child_value(self.product.properties, "alarm")
        if triggered is True:
            return CurrentModeToStateValue.TRIGGERED.value

        current_mode = get_child_value(self.product.properties, self.metadata.name, False)
        #if current_mode is False:
            #_LOGGER.debug(f"{self.product.name} current mode is missing, fallback to guardmode {self.guard_mode}")
        current_mode = get_child_value(self.product.properties, self.metadata.name, CurrentModeToState(self.guard_mode))

        if current_mode in CUSTOM_CODES:
            position = CUSTOM_CODES.index(current_mode)
            if position == 0:
                return self.coordinator.config.name_for_custom1
            if position == 1:
                return self.coordinator.config.name_for_custom2
            if position == 2:
                return self.coordinator.config.name_for_custom3
        try:
            state = CurrentModeToStateValue[CurrentModeToState(current_mode).name].value
        except KeyError:
            #_LOGGER.debug(f"{self.product.name} current mode is missing, fallback to Unknown with guard mode {self.guard_mode}")
            state = CurrentModeToStateValue.NONE.value
        return state
