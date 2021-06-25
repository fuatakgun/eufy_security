from enum import Enum

# Base component constants
NAME = "Eufy Security"
DOMAIN = "eufy_security"
VERSION = "0.0.0"

# Platforms
BINARY_SENSOR = "binary_sensor"
CAMERA = "camera"
SENSOR = "sensor"
PLATFORMS = [BINARY_SENSOR, CAMERA, SENSOR]

# Configuration and options
CONF_HOST = "host"
CONF_PORT = "port"

# Update all in every hour
DEFAULT_SYNC_INTERVAL = 60  # seconds
