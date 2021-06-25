from enum import Enum


class Device:
    name: str
    model: str
    serial_number: str
    hardware_version: str
    software_version: str
    station_serial_number: str
    enabled: bool
    state: int
    battery: int
    battery_temperature: int
    last_charging_days: int
    last_charging_total_events: int
    last_charging_recorded_events: int
    last_charging_false_events: int
    battery_usage_last_week: int
    motion_detected: bool
    person_detected: bool
    person_name: str
    antitheft_detection: bool
    auto_nightvision: bool
    led_status: bool
    motion_detection: bool
    rtsp_stream: bool
    watermark: int
    wifi_rssi: int
    picture_url: str

    def __init__(
        self,
        name: str,
        model: str,
        serial_number: str,
        hardware_version: str,
        software_version: str,
        station_serial_number: str,
        enabled: bool,
        state: int,
        battery: int,
        battery_temperature: int,
        last_charging_days: int,
        last_charging_total_events: int,
        last_charging_recorded_events: int,
        last_charging_false_events: int,
        battery_usage_last_week: int,
        motion_detected: bool,
        person_detected: bool,
        person_name: str,
        antitheft_detection: bool,
        auto_nightvision: bool,
        led_status: bool,
        motion_detection: bool,
        rtsp_stream: bool,
        watermark: int,
        wifi_rssi: int,
        picture_url: str,
    ) -> None:
        self.name = name
        self.model = model
        self.serial_number = serial_number
        self.hardware_version = hardware_version
        self.software_version = software_version
        self.station_serial_number = station_serial_number
        self.enabled = enabled
        self.state = state
        self.battery = battery
        self.battery_temperature = battery_temperature
        self.last_charging_days = last_charging_days
        self.last_charging_total_events = last_charging_total_events
        self.last_charging_recorded_events = last_charging_recorded_events
        self.last_charging_false_events = last_charging_false_events
        self.battery_usage_last_week = battery_usage_last_week
        self.motion_detected = motion_detected
        self.person_detected = person_detected
        self.person_name = person_name
        self.antitheft_detection = antitheft_detection
        self.auto_nightvision = auto_nightvision
        self.led_status = led_status
        self.motion_detection = motion_detection
        self.rtsp_stream = rtsp_stream
        self.watermark = watermark
        self.wifi_rssi = wifi_rssi
        self.picture_url = picture_url
