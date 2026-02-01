"""Department mapping between museums.

This module provides bidirectional mapping between canonical department names
(shown in the UI) and museum-specific department names (used in API queries).

When adding a new museum, add its mappings to DEPARTMENT_MAP using the
museum's short_name in lowercase as the key.
"""

from __future__ import annotations

# Canonical department names shown in the UI
# These are designed to be intuitive groupings that map reasonably
# to both CMA and AIC department structures
CANONICAL_DEPARTMENTS = [
    "African Art",
    "American Art",
    "Ancient Near Eastern Art",
    "Asian Art",
    "Contemporary Art",
    "Decorative Arts",
    "Drawings",
    "Egyptian Art",
    "European Art",
    "Greek and Roman Art",
    "Islamic Art",
    "Medieval Art",
    "Modern Art",
    "Photography",
    "Prints",
    "Textiles",
]

# Maps canonical name -> {museum_short_name: museum_specific_value}
# Values can be:
#   - str: exact match
#   - list[str]: any of these values (OR logic)
#   - None: not available for this museum
DEPARTMENT_MAP: dict[str, dict[str, str | list[str] | None]] = {
    "African Art": {
        "cma": "African Art",
        "aic": "Arts of Africa",
    },
    "American Art": {
        "cma": "American Painting and Sculpture",
        "aic": "American Art",
    },
    "Ancient Near Eastern Art": {
        "cma": "Egyptian and Ancient Near Eastern Art",
        "aic": "Ancient and Byzantine Art",
    },
    "Asian Art": {
        "cma": ["Chinese Art", "Japanese Art", "Korean Art", "Indian and South East Asian Art"],
        "aic": "Asian Art",
    },
    "Contemporary Art": {
        "cma": "Contemporary Art",
        "aic": "Contemporary Art",
    },
    "Decorative Arts": {
        "cma": "Decorative Art and Design",
        "aic": "Applied Arts of Europe",
    },
    "Drawings": {
        "cma": "Drawings",
        "aic": "Prints and Drawings",  # AIC combines these
    },
    "Egyptian Art": {
        "cma": "Egyptian and Ancient Near Eastern Art",
        "aic": "Ancient and Byzantine Art",
    },
    "European Art": {
        "cma": ["European Painting and Sculpture", "Modern European Painting and Sculpture"],
        "aic": ["Painting and Sculpture of Europe", "European Decorative Arts"],
    },
    "Greek and Roman Art": {
        "cma": "Greek and Roman Art",
        "aic": "Ancient and Byzantine Art",
    },
    "Islamic Art": {
        "cma": "Islamic Art",
        "aic": "Islamic Art",
    },
    "Medieval Art": {
        "cma": "Medieval Art",
        "aic": "Medieval Art",
    },
    "Modern Art": {
        "cma": "Modern European Painting and Sculpture",
        "aic": "Modern Art",
    },
    "Photography": {
        "cma": "Photography",
        "aic": "Photography and Media",
    },
    "Prints": {
        "cma": "Prints",
        "aic": "Prints and Drawings",  # AIC combines these
    },
    "Textiles": {
        "cma": "Textiles",
        "aic": "Textiles",
    },
}

# Reverse mapping: museum-specific -> canonical
# Built dynamically from DEPARTMENT_MAP
_REVERSE_MAP: dict[str, dict[str, str]] = {}


def _build_reverse_map() -> None:
    """Build reverse mapping from museum-specific to canonical names."""
    global _REVERSE_MAP
    _REVERSE_MAP = {}
    
    for canonical, museums in DEPARTMENT_MAP.items():
        for museum, value in museums.items():
            if museum not in _REVERSE_MAP:
                _REVERSE_MAP[museum] = {}
            
            if value is None:
                continue
            elif isinstance(value, list):
                for v in value:
                    _REVERSE_MAP[museum][v.lower()] = canonical
            else:
                _REVERSE_MAP[museum][value.lower()] = canonical


# Build reverse map on module load
_build_reverse_map()


def get_canonical_departments() -> list[str]:
    """Return list of canonical department names for UI display."""
    return CANONICAL_DEPARTMENTS.copy()


def map_to_museum(canonical: str, museum: str) -> str | list[str] | None:
    """
    Map a canonical department name to museum-specific value(s).
    
    Args:
        canonical: Canonical department name from UI
        museum: Museum short name (lowercase, e.g., "cma", "aic")
    
    Returns:
        - str: Single museum-specific department name
        - list[str]: Multiple valid department names (use OR logic)
        - None: No mapping available for this museum
    """
    museum = museum.lower()
    mapping = DEPARTMENT_MAP.get(canonical, {})
    return mapping.get(museum)


def map_from_museum(museum_dept: str, museum: str) -> str | None:
    """
    Map a museum-specific department name to canonical name.
    
    Args:
        museum_dept: Department name from museum API
        museum: Museum short name (lowercase, e.g., "cma", "aic")
    
    Returns:
        Canonical department name, or None if no mapping found
    """
    museum = museum.lower()
    if museum not in _REVERSE_MAP:
        return None
    return _REVERSE_MAP[museum].get(museum_dept.lower())
