"""Canonical genre and department mappings between museums.

This module maps canonical UI genres to museum-specific department values
used by source APIs.
"""

from __future__ import annotations

# Canonical genre names shown in the UI.
CANONICAL_GENRES = [
    "African Art",
    "American Art",
    "Ancient Near Eastern Art",
    "Asian Art",
    "Contemporary Art",
    "Egyptian Art",
    "European Art",
    "Greek and Roman Art",
    "Islamic Art",
    "Medieval Art",
    "Modern Art",
]

# Canonical medium names shown in the UI.
CANONICAL_MEDIA = [
    "Decorative Arts",
    "Drawings",
    "Painting",
    "Photography",
    "Prints",
    "Sculpture",
    "Textiles",
]

# Backward-compatible alias for callers that still refer to "departments".
CANONICAL_DEPARTMENTS = CANONICAL_GENRES

# Maps canonical genre -> {museum_short_name: museum_specific_value}
# Values can be:
#   - str: exact match
#   - list[str]: any of these values (OR logic)
#   - None: not available for this museum
DEPARTMENT_MAP: dict[str, dict[str, str | list[str] | None]] = {
    "African Art": {
        "cma": "African Art",
        "aic": "Arts of Africa",
        "moma": ["africa", "african"],
    },
    "American Art": {
        "cma": ["American Painting and Sculpture", "Art of the Americas"],
        "aic": ["American Art", "Arts of the Americas"],
        "moma": ["american", "united states", "u.s.", "usa"],
    },
    "Ancient Near Eastern Art": {
        "cma": "Egyptian and Ancient Near Eastern Art",
        "aic": "Ancient and Byzantine Art",
        "moma": ["ancient", "near eastern", "mesopotamia", "assyrian"],
    },
    "Asian Art": {
        "cma": ["Chinese Art", "Japanese Art", "Korean Art", "Indian and South East Asian Art"],
        "aic": "Asian Art",
        "moma": ["asian", "china", "chinese", "japan", "japanese", "korea", "korean", "india", "indian"],
    },
    "Contemporary Art": {
        "cma": "Contemporary Art",
        "aic": "Contemporary Art",
        "moma": "contemporary",
    },
    "Egyptian Art": {
        "cma": "Egyptian and Ancient Near Eastern Art",
        "aic": "Ancient and Byzantine Art",
        "moma": ["egypt", "egyptian"],
    },
    "European Art": {
        "cma": ["European Painting and Sculpture", "Modern European Painting and Sculpture"],
        "aic": ["Painting and Sculpture of Europe", "European Decorative Arts"],
        "moma": ["europe", "european", "france", "french", "italy", "italian", "germany", "german", "spain", "spanish", "britain", "english", "dutch"],
    },
    "Greek and Roman Art": {
        "cma": "Greek and Roman Art",
        "aic": "Ancient and Byzantine Art",
        "moma": ["greek", "roman"],
    },
    "Islamic Art": {
        "cma": "Islamic Art",
        "aic": "Islamic Art",
        "moma": "islamic",
    },
    "Medieval Art": {
        "cma": "Medieval Art",
        "aic": "Medieval Art",
        "moma": "medieval",
    },
    "Modern Art": {
        "cma": ["Modern European Painting and Sculpture", "Contemporary Art"],
        "aic": ["Modern Art", "Contemporary Art"],
        "moma": "modern",
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


def get_canonical_genres() -> list[str]:
    """Return canonical genre options for UI display."""
    return CANONICAL_GENRES.copy()


def get_canonical_media() -> list[str]:
    """Return canonical medium options for UI display."""
    return CANONICAL_MEDIA.copy()


def get_canonical_departments() -> list[str]:
    """Backward-compatible alias for canonical genres."""
    return get_canonical_genres()


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
