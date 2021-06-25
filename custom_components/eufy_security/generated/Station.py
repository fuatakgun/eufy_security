from .GuardMode import GuardMode


class Station:
    name: str
    model: str
    serial_number: str
    hardware_version: str
    software_version: str
    lan_ip_address: str
    mac_address: str
    current_mode: int
    guard_mode: int
    connected: bool

    def __init__(
        self,
        name: str,
        model: str,
        serial_number: str,
        hardware_version: str,
        software_version: str,
        lan_ip_address: str,
        mac_address: str,
        current_mode: int,
        guard_mode: int,
        connected: bool,
    ) -> None:
        self.name = name
        self.model = model
        self.serial_number = serial_number
        self.hardware_version = hardware_version
        self.software_version = software_version
        self.lan_ip_address = lan_ip_address
        self.mac_address = mac_address
        self.current_mode = GuardMode(current_mode)
        self.guard_mode: GuardMode = GuardMode(guard_mode)
        self.connected = connected
