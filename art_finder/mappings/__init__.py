"""Department and field mappings across museums."""

from .departments import (
    CANONICAL_DEPARTMENTS,
    get_canonical_departments,
    map_to_museum,
    map_from_museum,
)

__all__ = [
    "CANONICAL_DEPARTMENTS",
    "get_canonical_departments", 
    "map_to_museum",
    "map_from_museum",
]
