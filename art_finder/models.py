"""Data models for Art Finder application."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Artwork:
    """Unified artwork representation across all museum sources."""
    
    id: str
    source: str  # Museum short name (e.g., "CMA", "AIC")
    title: str
    artist: str
    image_url: str
    filename: str  # Suggested download filename
    
    # Optional fields with defaults
    date: str = ""
    medium: str = ""
    department: str = ""
    classification: str = ""
    credit: str = ""
    culture: str = ""
    dimensions: str = ""
    description: str = ""
    accession_number: str = ""
    
    # Image dimensions (for orientation/resolution filtering)
    image_width: int | None = None
    image_height: int | None = None
    
    # Museum-specific extras
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for session state storage."""
        return {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "artist": self.artist,
            "image_url": self.image_url,
            "filename": self.filename,
            "date": self.date,
            "medium": self.medium,
            "department": self.department,
            "classification": self.classification,
            "credit": self.credit,
            "culture": self.culture,
            "dimensions": self.dimensions,
            "description": self.description,
            "accession_number": self.accession_number,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "metadata": self.metadata,
        }


@dataclass
class SearchFilters:
    """Unified search filters that adapters translate to API-specific params."""
    
    query: str | None = None
    year_from: int | None = None
    year_to: int | None = None
    department: str | None = None  # Canonical department name
    orientation: str | None = None  # "Portrait" or "Landscape"
    min_width: int | None = None
    min_height: int | None = None
    has_image: bool = True
    limit: int = 100
    
    # SSL bypass for debugging
    ssl_bypass: bool = False


@dataclass
class FilterStatus:
    """Tracks which filters were applied vs skipped."""
    
    applied: dict[str, str] = field(default_factory=dict)  # filter -> description
    skipped: dict[str, str] = field(default_factory=dict)  # filter -> reason


@dataclass
class AdapterResult:
    """Result from an adapter search, including any errors or warnings."""
    
    artworks: list[Artwork] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)  # User-friendly error messages
    warnings: list[str] = field(default_factory=list)  # Non-fatal issues
    filter_status: FilterStatus = field(default_factory=FilterStatus)
    
    @property
    def success(self) -> bool:
        """True if we got results without fatal errors."""
        return len(self.artworks) > 0 or len(self.errors) == 0
    
    @property
    def has_warnings(self) -> bool:
        """True if there are warnings or skipped filters."""
        return len(self.warnings) > 0 or len(self.filter_status.skipped) > 0
