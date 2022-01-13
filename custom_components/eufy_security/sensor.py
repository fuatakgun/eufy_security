import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    PERCENTAGE,
)
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
        (
            "battery",
            "Battery",
            "state.battery",
            PERCENTAGE,
            None,
            DEVICE_CLASS_BATTERY,
            EntityCategory.DIAGNOSTIC,
        ),
        (
            "wifiRSSI",
            "Wifi RSSI",
            "state.wifiRSSI",
            None,
            None,
            DEVICE_CLASS_SIGNAL_STRENGTH,
            EntityCategory.DIAGNOSTIC,
        ),
        (
            "detected_person_name",
            "Detected Person Name",
            "state.personName",
            None,
            None,
            None,
            None,
        ),
    ]

    CAMERA_INSTRUMENTS = [
        (
            "stream_source_type",
            "Streaming Source Type",
            "stream_source_type",
            None,
            None,
            None,
            EntityCategory.DIAGNOSTIC,
        ),
        (
            "stream_source_address",
            "Streaming Source Address",
            "stream_source_address",
            None,
            None,
            None,
            EntityCategory.DIAGNOSTIC,
        ),
        ("codec", "Codec", "codec", None, None, None, EntityCategory.DIAGNOSTIC),
        (
            "stream_queue_size",
            "Stream Queue Size",
            "queue",
            None,
            None,
            None,
            EntityCategory.DIAGNOSTIC,
        ),
    ]

    entities = []
    for device in coordinator.devices.values():
        instruments = INSTRUMENTS
        if device.is_camera() is True:
            instruments = instruments + CAMERA_INSTRUMENTS
        for (
            id,
            description,
            key,
            unit,
            icon,
            device_class,
            entity_category,
        ) in instruments:
            if not get_child_value(device.__dict__, key) is None:
                entities.append(
                    EufySecuritySensor(
                        coordinator,
                        config_entry,
                        device,
                        id,
                        description,
                        key,
                        unit,
                        icon,
                        device_class,
                        entity_category,
                    )
                )

    async_add_devices(entities, True)


class EufySecuritySensor(EufySecurityEntity):
    def __init__(
        self,
        coordinator: EufySecurityDataUpdateCoordinator,
        config_entry: ConfigEntry,
        device: Device,
        id: str,
        description: str,
        key: str,
        unit: str,
        icon: str,
        device_class: str,
        entity_category: str,
    ):
        super().__init__(coordinator, config_entry, device)
        self._id = id
        self.description = description
        self.key = key
        self.unit = unit
        self._icon = icon
        self._device_class = device_class
        self._attr_entity_category = entity_category

    @property
    def state(self):
        if self._id == "stream_queue_size":
            return self.device.queue.qsize()
        return get_child_value(self.device.__dict__, self.key)

    @property
    def unit_of_measurement(self):
        return self.unit

    @property
    def icon(self):
        return self._icon

    @property
    def device_class(self):
        return self._device_class

    @property
    def name(self):
        return f"{self.device.name} {self.description}"

    @property
    def id(self):
        return f"{DOMAIN}_{self.device.serial_number}_{self._id}_sensor"

    @property
    def unique_id(self):
        return self.id
