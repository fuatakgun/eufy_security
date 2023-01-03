from dataclasses import dataclass


@dataclass
class MetadataFilter:
    """Property Metadata"""

    readable: bool
    writeable: bool
    types: []
    any_fields: [] = None
    no_fields: [] = None
