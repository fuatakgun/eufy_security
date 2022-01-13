import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import COORDINATOR, DOMAIN, Device, get_child_value
from .coordinator import EufySecurityDataUpdateCoordinator
from .entity import EufySecurityEntity

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_devices
):
    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN][COORDINATOR]

    INSTRUMENTS = [
        ("night_vision", "Night Vision", "nightvision"),
        ("power_working_mode", "Power Working Mode", "powerWorkingMode"),
        ("video_streaming_quality", "Video Streaming Quality", "videoStreamingQuality"),
        ("video_recording_quality", "Video Recording Quality", "videoRecordingQuality"),
        ("motion_detection_type", "Motion Detection Type", "motionDetectionType"),
        ("rotation_speed", "Rotation Speed", "rotationSpeed"),
    ]

    entities = []
    for device in coordinator.devices.values():
        instruments = INSTRUMENTS
        for id, description, key in instruments:
            if not get_child_value(device.state, key) is None:
                entities.append(
                    EufySelectEntity(
                        coordinator, config_entry, device, id, description, key
                    )
                )

    async_add_devices(entities, True)


class EufySelectEntity(EufySecurityEntity, SelectEntity):
    def __init__(
        self,
        coordinator: EufySecurityDataUpdateCoordinator,
        config_entry: ConfigEntry,
        device: Device,
        id: str,
        description: str,
        key: str,
    ):
        EufySecurityEntity.__init__(self, coordinator, config_entry, device)
        SelectEntity.__init__(self)
        self._id = id
        self.description = description
        self.key = key
        self.states = get_child_value(self.device.properties_metadata, self.key)
        _LOGGER.debug(
            f"{DOMAIN} - {self.device.name} - {self.id} - select init - {self.states}"
        )
        self.values_to_states = self.states.get("states", {})
        self.states_to_values = {v: k for k, v in self.values_to_states.items()}
        self._attr_options: list[str] = list(self.values_to_states.values())

        _LOGGER.debug(
            f"{DOMAIN} - {self.device.name} - {self.id} - select init - {self.values_to_states} - {self.states_to_values}"
        )

    async def async_select_option(self, option: str):
        await self.coordinator.async_set_property(
            self.device.serial_number, self.key, self.states_to_values[option]
        )

    @property
    def current_option(self) -> str:
        current_value = str(get_child_value(self.device.state, self.key))
        current_option = self.values_to_states.get(current_value, None)
        if current_option is None:
            _LOGGER.error(
                f"{DOMAIN} - {self.device.name} - {self.id} - missing value - value: {current_value} - values_to_states: {self.values_to_states} - states_to_values: {self.states_to_values} - "
            )
        return current_option

    @property
    def name(self):
        return f"{self.device.name} {self.description}"

    @property
    def id(self):
        return f"{DOMAIN}_{self.device.serial_number}_{self._id}_select"

    @property
    def unique_id(self):
        return self.id
