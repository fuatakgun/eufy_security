import logging

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME, PropertyToEntityDescription
from .coordinator import EufySecurityDataUpdateCoordinator
from .eufy_security_api.metadata import Metadata
from .eufy_security_api.product import Product

_LOGGER: logging.Logger = logging.getLogger(__package__)


class EufySecurityEntity(CoordinatorEntity):
    """Base entity for integration"""

    def __init__(
        self,
        coordinator: EufySecurityDataUpdateCoordinator,
        metadata: Metadata,
    ) -> None:
        super().__init__(coordinator)
        self.metadata: Metadata = metadata
        self.product.set_state_update_listener(coordinator.async_update_listeners)

        self._attr_unique_id = f"{DOMAIN}_{self.product.serial_no}_{metadata.name}"
        self._attr_should_poll = False
        self._attr_icon = self.description.icon
        self._attr_name = f"{self.product.name} {metadata.label}"
        self._attr_device_class = self.description.device_class
        self._attr_entity_category = self.description.category

    @property
    def product(self) -> Product:
        """Get product instance of entity"""
        return self.metadata.product

    @property
    def description(self) -> PropertyToEntityDescription:
        """Get description of entity"""
        return PropertyToEntityDescription[self.metadata.name].value

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.product.serial_no)},
            "name": self.product.name,
            "model": self.product.model,
            "hardware": self.product.hardware_version,
            "software": self.product.software_version,
            "manufacturer": NAME,
        }
