"""Museum-specific field enums and metadata for Help page visualization.

These values are derived from museum CSV exports and hardcoded here for
display purposes. They are NOT used at runtime for filtering — that logic
lives in departments.py and the adapters.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# CMA — Cleveland Museum of Art
# ---------------------------------------------------------------------------

CMA_DEPARTMENTS: list[str] = [
    "African Art",
    "American Painting and Sculpture",
    "Art of the Americas",
    "Chinese Art",
    "Contemporary Art",
    "Decorative Art and Design",
    "Drawings",
    "Egyptian and Ancient Near Eastern Art",
    "European Painting and Sculpture",
    "Greek and Roman Art",
    "Indian and Southeast Asian Art",
    "Islamic Art",
    "Japanese Art",
    "Korean Art",
    "Medieval Art",
    "Modern European Painting and Sculpture",
    "Photography",
    "Prints",
    "Textiles",
]

CMA_TYPES: list[str] = [
    "Amulets",
    "Arms and Armor",
    "Bound Volume",
    "Carpet",
    "Ceramic",
    "Cosmetic Objects",
    "Drawing",
    "Enamel",
    "Funerary Equipment",
    "Furniture and woodwork",
    "Garment",
    "Glass",
    "Glyptic",
    "Implements",
    "Inlays",
    "Ivory",
    "Jade",
    "Jewelry",
    "Lacquer",
    "Lamp",
    "Manuscript",
    "Mask",
    "Metalwork",
    "Miscellaneous",
    "Mixed Media",
    "Mosaic",
    "Painting",
    "Photograph",
    "Portrait Miniature",
    "Print",
    "Sculpture",
    "Silver",
    "Tapestry",
    "Textile",
    "Time-based Media",
    "Timepiece",
    "Vessels",
    "Wood",
]

# ---------------------------------------------------------------------------
# AIC — Art Institute of Chicago
# ---------------------------------------------------------------------------

AIC_DEPARTMENTS: list[str] = [
    "AIC Archives",
    "Applied Arts of Europe",
    "Architecture and Design",
    "Arts of Africa",
    "Arts of Asia",
    "Arts of Greece, Rome, and Byzantium",
    "Arts of the Americas",
    "Contemporary Art",
    "Modern Art",
    "Painting and Sculpture of Europe",
    "Photography and Media",
    "Prints and Drawings",
    "Ryerson and Burnham Libraries Special Collections",
    "Textiles",
]

# ---------------------------------------------------------------------------
# MoMA — Museum of Modern Art
# ---------------------------------------------------------------------------

MOMA_DEPARTMENTS: list[str] = [
    "Architecture & Design",
    "Architecture & Design - Image Archive",
    "Drawings & Prints",
    "Film",
    "Fluxus Collection",
    "Media and Performance",
    "Painting & Sculpture",
    "Photography",
]

MOMA_CLASSIFICATIONS: list[str] = [
    "(not assigned)",
    "Architectural Model",
    "Architecture",
    "Audio",
    "Collage",
    "Correspondence",
    "Design",
    "Digital",
    "Document",
    "Drawing",
    "Ephemera",
    "Fashion",
    "Film",
    "Film (object)",
    "Frank Lloyd Wright Archive",
    "Furniture and Interiors",
    "Graphic Design",
    "Illustrated Book",
    "Installation",
    "Media",
    "Mies van der Rohe Archive",
    "Moving Image",
    "Multiple",
    "News Clipping",
    "Notebook",
    "Painting",
    "Performance",
    "Periodical",
    "Photo Album",
    "Photograph",
    "Photography Research/Reference",
    "Portfolio",
    "Poster",
    "Print",
    "Publication",
    "Sculpture",
    "Software",
    "Textile",
    "Video",
    "Wallpaper",
    "Website",
    "Work on Paper",
]

MOMA_MEDIUM_SAMPLES: list[str] = [
    "Oil on canvas",
    "Gelatin silver print",
    "Lithograph",
    "Ink and cut-and-pasted painted pages on paper",
    "Graphite on paper",
    "Gouache on paper",
    "Screenprint",
    "Etching",
    "Chromogenic print",
    "Woodcut",
]

MOMA_MEDIUM_MATCH_LOGIC: str = (
    "Free-text field (23K+ unique values). "
    "Matched via case-insensitive keyword contains."
)

# ---------------------------------------------------------------------------
# Medium keyword map — per-museum keywords for each canonical medium
# ---------------------------------------------------------------------------

MEDIUM_KEYWORD_MAP: dict[str, dict[str, list[str]]] = {
    "Decorative Arts": {
        "cma": ["decorative", "design", "furniture"],
        "aic": ["decorative", "applied arts"],
        "moma": ["decorative", "design", "furniture"],
    },
    "Drawings": {
        "cma": ["drawing"],
        "aic": ["drawing"],
        "moma": ["drawing"],
    },
    "Painting": {
        "cma": ["painting"],
        "aic": ["painting"],
        "moma": ["painting"],
    },
    "Photography": {
        "cma": ["photography", "photo"],
        "aic": ["photograph", "photo"],
        "moma": ["photograph", "photo"],
    },
    "Prints": {
        "cma": ["print", "etching", "lithograph", "woodcut"],
        "aic": ["print", "etching", "lithograph", "woodcut"],
        "moma": ["print", "etching", "lithograph", "woodcut"],
    },
    "Sculpture": {
        "cma": ["sculpture", "statue"],
        "aic": ["sculpture", "statue"],
        "moma": ["sculpture", "statue"],
    },
    "Textiles": {
        "cma": ["textile", "fabric", "tapestry"],
        "aic": ["textile", "fabric", "tapestry"],
        "moma": ["textile", "fabric", "tapestry"],
    },
}

# ---------------------------------------------------------------------------
# Per-museum field metadata — which source fields map to which concepts
# ---------------------------------------------------------------------------

MUSEUM_FIELD_MAP: dict[str, dict[str, dict]] = {
    "CMA": {
        "genre": {
            "source_fields": ["department"],
            "enum": CMA_DEPARTMENTS,
            "match": "exact (API param) or client-side OR",
        },
        "medium": {
            "source_fields": ["technique", "type", "department"],
            "enum_type": "mixed",
            "enum": CMA_TYPES,
            "match": "keyword contains",
        },
    },
    "AIC": {
        "genre": {
            "source_fields": ["department_title"],
            "enum": AIC_DEPARTMENTS,
            "match": "client-side case-insensitive contains",
        },
        "medium": {
            "source_fields": ["medium_display", "classification_title", "department_title"],
            "enum_type": "free-text",
            "match": "keyword contains",
        },
    },
    "MoMA": {
        "genre": {
            "source_fields": ["Department", "Classification", "Medium", "Nationality", "ArtistBio"],
            "enum": MOMA_DEPARTMENTS,
            "match": "client-side keyword contains across multiple fields",
        },
        "medium": {
            "source_fields": ["Medium", "Classification", "Department"],
            "enum_type": "free-text",
            "samples": MOMA_MEDIUM_SAMPLES,
            "match": MOMA_MEDIUM_MATCH_LOGIC,
        },
    },
}
