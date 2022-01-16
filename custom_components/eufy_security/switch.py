import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from .const import COORDINATOR, DOMAIN, Device, get_child_value
from .coordinator import EufySecurityDataUpdateCoordinator
from .entity import EufySecurityEntity

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_devices
):
    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN][COORDINATOR]

    INSTRUMENTS = [
        ("enabled", "Enabled", "enabled", EntityCategory.CONFIG),
        (
            "motion_detection",
            "Motion Detection",
            "motionDetection",
            EntityCategory.CONFIG,
        ),
        ("motion_tracking", "Motion Tracking", "motionTracking", EntityCategory.CONFIG),
        (
            "person_detection",
            "Person Detection",
            "personDetection",
            EntityCategory.CONFIG,
        ),
        ("pet_detection", "Pet Detection", "petDetection", EntityCategory.CONFIG),
        (
            "crying_detection",
            "Crying Detection",
            "cryingDetection",
            EntityCategory.CONFIG,
        ),
        ("indoor_chime", "Indoor Chime", "chimeIndoor", EntityCategory.CONFIG),
        ("status_led", "Status Led", "statusLed", EntityCategory.CONFIG),
        (
            "anti_theft_detection",
            "Anti Theft Detection",
            "antitheftDetection",
            EntityCategory.CONFIG,
        ),
        (
            "auto_night_vision",
            "Auto Night Vision",
            "autoNightvision",
            EntityCategory.CONFIG,
        ),
        ("night_vision", "Night Vision", "nightvision", EntityCategory.CONFIG),
        ("microphone", "Microphone", "microphone", EntityCategory.CONFIG),
        ("speaker", "Speaker", "speaker", EntityCategory.CONFIG),
        ("audio_recording", "Audio Recording", "audioRecording", EntityCategory.CONFIG),
        ("sound_detection", "Sound Detection", "soundDetection", EntityCategory.CONFIG),
        ("light", "Light", "light", EntityCategory.CONFIG),
        ("rtsp_stream", "RTSP Stream", "rtspStream", EntityCategory.CONFIG),
    ]

    entities = []
    for device in coordinator.devices.values():
        instruments = INSTRUMENTS
        for id, description, key, entity_category in instruments:
            if not get_child_value(device.state, key) is None:
                entities.append(
                    EufySwitchEntity(
                        coordinator,
                        config_entry,
                        device,
                        id,
                        description,
                        key,
                        "False",
                        "True",
                        entity_category,
                    )
                )

    async_add_devices(entities, True)


class EufySwitchEntity(EufySecurityEntity, SwitchEntity):
    def __init__(
        self,
        coordinator: EufySecurityDataUpdateCoordinator,
        config_entry: ConfigEntry,
        device: Device,
        id: str,
        description: str,
        key: str,
        off_value: str,
        on_value: str,
        entity_category: str,
    ):
        EufySecurityEntity.__init__(self, coordinator, config_entry, device)
        SwitchEntity.__init__(self)
        self._id = id
        self.description = description
        self.key = key
        self.off_value = str(off_value)
        self.on_value = str(on_value)
        self._attr_entity_category = entity_category

    @property
    def is_on(self):
        value = str(get_child_value(self.device.state, self.key))
        if value == self.off_value:
            return False
        if value == self.on_value:
            return True
        return None

    async def async_turn_off(self):
        await self.coordinator.async_set_property(
            self.device.serial_number, self.key, self.off_value
        )

    async def async_turn_on(self):
        await self.coordinator.async_set_property(
            self.device.serial_number, self.key, self.on_value
        )

    @property
    def name(self):
        return f"{self.device.name} {self.description}"

    @property
    def id(self):
        return f"{DOMAIN}_{self.device.serial_number}_{self._id}_switch"

    @property
    def unique_id(self):
        return self.id
