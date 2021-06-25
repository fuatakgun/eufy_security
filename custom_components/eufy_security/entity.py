import logging

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME, VERSION
from .coordinator import EufySecurityDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)


class EufySecurityEntity(CoordinatorEntity):
    def __init__(
        self, coordinator: EufySecurityDataUpdateCoordinator, entry, entity: dict
    ):
        super().__init__(coordinator)
        self.entry = entry
        self.entity = entity

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.entity["serialNumber"])},
            "name": self.entity["name"],
            "model": self.entity["model"],
            "hardware": self.entity["hardwareVersion"],
            "software": self.entity["softwareVersion"],
            "manufacturer": NAME,
        }

    @property
    def available(self) -> bool:
        return not not self.coordinator.data

    @property
    def should_poll(self) -> bool:
        return False
