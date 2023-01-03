from dataclasses import dataclass, field


@dataclass
class Event:
    """Event"""

    type: str
    data: dict = field(default_factory=dict)
