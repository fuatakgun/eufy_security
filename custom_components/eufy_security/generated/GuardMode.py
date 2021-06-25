from enum import Enum


class GuardMode(Enum):
    AWAY = 0
    HOME = 1
    SCHEDULE = 2
    CUSTOM1 = 3
    CUSTOM2 = 4
    CUSTOM3 = 5
    OFF = 6
    GEO = 47
    DISARMED = 63
