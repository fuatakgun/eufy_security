from dataclasses import dataclass
from enum import auto, Enum, StrEnum

from homeassistant.config_entries import ConfigEntry


@dataclass
class EntityDescription:
    """Entity Description"""

    id: str
    icon: str = None
    state_class: StrEnum = None
    device_class: StrEnum = None
    unit: str = None
    category: StrEnum = None


class ConfigField(Enum):
    """Config and Options Fields"""

    host = "127.0.0.1"
    port = 3000
    sync_interval = 600  # seconds
    rtsp_server_address = 3
    no_stream_in_hass = False
    name_for_custom1 = "Custom 1"
    name_for_custom2 = "Custom 2"
    name_for_custom3 = "Custom 3"
    captcha_id = 8
    captcha_img = 9
    captcha_input = 10
    mfa_required = 11
    mfa_input = 12


@dataclass
class Config:
    """Integration config options"""

    entry: ConfigEntry = None
    host: str = ConfigField.host.value
    port: int = ConfigField.port.value
    sync_interval: int = ConfigField.sync_interval.value
    rtsp_server_address: str = ConfigField.host.value
    no_stream_in_hass: bool = ConfigField.no_stream_in_hass.value
    name_for_custom1: str = ConfigField.name_for_custom1.value
    name_for_custom2: str = ConfigField.name_for_custom2.value
    name_for_custom3: str = ConfigField.name_for_custom3.value
    captcha_id: str = None
    captcha_img: str = None
    captcha_input: str = None
    mfa_required: bool = False
    mfa_input: str = None

    @classmethod
    def parse(cls, config_entry: ConfigEntry):
        """Generate config instance from config entry"""
        data_keys = ["host", "port"]
        config = cls()
        config.entry = config_entry
        for key in config.__dict__:
            if key in data_keys:
                if config_entry.data.get(key, None) is not None:
                    config.__dict__[key] = config_entry.data.get(key)
            else:
                if config_entry.options.get(key, None) is not None:
                    config.__dict__[key] = config_entry.options.get(key)
        return config
