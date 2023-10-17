import logging

from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, PropertyToEntityDescription
from .coordinator import EufySecurityDataUpdateCoordinator
from .eufy_security_api.metadata import Metadata
from .eufy_security_api.product import Product
from .util import get_device_info

_LOGGER: logging.Logger = logging.getLogger(__package__)


class EufySecurityEntity(CoordinatorEntity):
    """Base entity for integration"""

    def __init__(self, coordinator: EufySecurityDataUpdateCoordinator, metadata: Metadata) -> None:
        super().__init__(coordinator)
        self.metadata: Metadata = metadata
        self.product.set_state_update_listener(coordinator.async_update_listeners)
        self._attr_unique_id = f"{DOMAIN}_{self.product.serial_no}_{self.product.product_type.value}_{metadata.name}"
        self._attr_should_poll = False
        self._attr_icon = self.description.icon
        self._attr_name = f"{self.product.name} {metadata.label}"
        self._attr_device_class = self.description.device_class
        self._attr_entity_category = self.description.category
        self._attr_entity_registry_enabled_default = False if self._attr_entity_category == EntityCategory.DIAGNOSTIC else True

    @property
    def product(self) -> Product:
        """Get product instance of entity"""
        return self.metadata.product

    @property
    def description(self) -> PropertyToEntityDescription:
        """Get description of entity"""
        try:
            return PropertyToEntityDescription[self.metadata.name].value
        except KeyError:
            return PropertyToEntityDescription.default.value

    @property
    def device_info(self):
        return get_device_info(self.product)

    @property
    def available(self) -> bool:
        return self.coordinator.available
