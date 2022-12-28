from dataclasses import dataclass


@dataclass
class CommandDescription:
    """Property Metadata"""

    description: str
    command: str = None
