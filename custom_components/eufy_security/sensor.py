import logging

from decimal import Decimal

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_SIGNAL_STRENGTH,
)

from .const import DOMAIN
from .entity import EufySecurityEntity
from .coordinator import EufySecurityDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass, entry, async_add_devices):
    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN]

    INSTRUMENTS = [
        (
            "battery",
            "Battery",
            "battery",
            PERCENTAGE,
            None,
            DEVICE_CLASS_BATTERY,
        ),
        (
            "wifiRSSI",
            "Wifi RSSI",
            "wifiRSSI",
            None,
            None,
            DEVICE_CLASS_SIGNAL_STRENGTH,
        ),
    ]

    entities = []
    for entity in coordinator.state["devices"]:
        for id, description, key, unit, icon, device_class in INSTRUMENTS:
            if not entity.get(key, None) is None:
                entities.append(
                    EufySecuritySensor(
                        coordinator,
                        entry,
                        entity,
                        id,
                        description,
                        key,
                        unit,
                        icon,
                        device_class,
                    )
                )

    async_add_devices(entities, True)


class EufySecuritySensor(EufySecurityEntity):
    def __init__(
        self,
        coordinator: EufySecurityDataUpdateCoordinator,
        entry: ConfigEntry,
        entity: dict,
        id: str,
        description: str,
        key: str,
        unit: str,
        icon: str,
        device_class: str,
    ):

        super().__init__(coordinator, entry, entity)
        self._id = id
        self.description = description
        self.key = key
        self.unit = unit
        self._icon = icon
        self._device_class = device_class

    @property
    def state(self):
        return self.entity.get(self.key)

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
        return f"{self.entity['name']} {self.description}"

    @property
    def id(self):
        return f"{DOMAIN}_{self.entity.get('serialNumber','missing_serial_number')}_{self._id}_sensor"

    @property
    def unique_id(self):
        return self.id

    @property
    def state_attributes(self):
        return self.entity
