import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import COORDINATOR, DOMAIN
from .coordinator import EufySecurityDataUpdateCoordinator
from .entity import EufySecurityEntity
from .eufy_security_api.metadata import Metadata
from .eufy_security_api.const import ProductCommand

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Setup binary sensor entities."""
    coordinator: EufySecurityDataUpdateCoordinator = hass.data[DOMAIN][COORDINATOR]
    product_properties = []
    for product in list(coordinator.devices.values()) + list(coordinator.stations.values()):
        for command in ProductCommand:
            handler_func = getattr(product, f"{command.name}", None)
            if handler_func is None:
                continue
            if command.value.command is not None:
                if command.value.command == "is_rtsp_enabled":
                    if product.is_rtsp_enabled is False:
                        continue
                else:
                    if command.value.command not in product.commands:
                        continue

            product_properties.append(
                Metadata.parse(product, {"name": command.name, "label": command.value.description, "command": command.value})
            )

    entities = [EufySecurityButtonEntity(coordinator, metadata) for metadata in product_properties]
    async_add_entities(entities)


class EufySecurityButtonEntity(ButtonEntity, EufySecurityEntity):
    """Base button entity for integration"""

    def __init__(self, coordinator: EufySecurityDataUpdateCoordinator, metadata: Metadata) -> None:
        super().__init__(coordinator, metadata)

    async def async_press(self) -> None:
        """Press the button."""
        handler_func = getattr(self.product, f"{self.metadata.name}")
        await handler_func()
