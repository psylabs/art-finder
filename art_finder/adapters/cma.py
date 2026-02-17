"""Cleveland Museum of Art adapter."""

from __future__ import annotations

import random
import secrets

import requests

from . import register
from .base import MuseumAdapter
from ..models import Artwork, SearchFilters, AdapterResult
from ..mappings.departments import map_to_museum


# CMA-specific department list
CMA_DEPARTMENTS = [
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
    "Indian and South East Asian Art",
    "Islamic Art",
    "Japanese Art",
    "Korean Art",
    "Medieval Art",
    "Modern European Painting and Sculpture",
    "Oceania",
    "Performing Arts, Music, & Film",
    "Photography",
    "Prints",
    "Textiles",
]


@register
class CMAAdapter(MuseumAdapter):
    """Adapter for the Cleveland Museum of Art Open Access API."""
    
    name = "Cleveland Museum of Art"
    short_name = "CMA"
    base_url = "https://openaccess-api.clevelandart.org/api/artworks"
    MEDIUM_KEYWORDS: dict[str, list[str]] = {
        "Decorative Arts": ["decorative", "design", "furniture"],
        "Drawings": ["drawing"],
        "Painting": ["painting"],
        "Photography": ["photography", "photo"],
        "Prints": ["print", "etching", "lithograph", "woodcut"],
        "Sculpture": ["sculpture", "statue"],
        "Textiles": ["textile", "fabric", "tapestry"],
    }
    
    def _do_search(self, filters: SearchFilters, result: AdapterResult) -> list[Artwork]:
        """Execute search against CMA API."""
        # Build API params
        params = {
            "has_image": 1,
            "limit": min(max(filters.limit * 3, filters.limit), 250),
        }
        dept_filter_values: set[str] | None = None

        if filters.query:
            params["q"] = filters.query
            result.filter_status.applied["query"] = f"Search term: {filters.query}"
        
        # Apply date filters if provided
        implicit_year_from = None
        if filters.department == "Modern Art" and filters.year_from is None:
            implicit_year_from = 1860
            params["created_after"] = implicit_year_from
            result.filter_status.applied["modern_year_guard"] = (
                "Modern Art defaulted to year >= 1860 (override with Year Range)."
            )
        if filters.year_from:
            params["created_after"] = filters.year_from
            result.filter_status.applied["year_from"] = f"Created after {filters.year_from}"
        
        if filters.year_to:
            params["created_before"] = filters.year_to
            result.filter_status.applied["year_to"] = f"Created before {filters.year_to}"
        
        # Apply department filter if provided
        if filters.department:
            cma_dept = map_to_museum(filters.department, "cma")
            if cma_dept:
                if isinstance(cma_dept, list):
                    dept_filter_values = set(cma_dept)
                    result.filter_status.skipped["department"] = (
                        "CMA API accepts one department value; used client-side OR filter "
                        f"for mapped departments ({', '.join(sorted(dept_filter_values))})"
                    )
                else:
                    params["department"] = cma_dept
                    result.filter_status.applied["department"] = f"Department: {cma_dept}"
            else:
                result.filter_status.skipped["department"] = (
                    f"No CMA mapping for '{filters.department}'"
                )

        if filters.medium:
            result.filter_status.applied["medium"] = f"Medium: {filters.medium} (client-side)"
        
        self._log_info(
            f"Fetching from CMA API (timeout={self.fetch_timeout}s, "
            f"ssl_bypass={filters.ssl_bypass}, limit={filters.limit})"
        )
        
        # Make the request
        response = requests.get(
            self.base_url,
            params=params,
            timeout=self.fetch_timeout,
            verify=not filters.ssl_bypass,
        )
        response.raise_for_status()
        
        data = response.json()
        artworks_data = data.get("data", [])
        
        self._log_info(f"Received {len(artworks_data)} artworks from API")
        
        # Process and filter artworks
        artworks: list[Artwork] = []
        dept_filtered = 0
        medium_filtered = 0
        orientation_filtered = 0
        resolution_filtered = 0
        
        for item in artworks_data:
            try:
                # Get image URL
                images = item.get("images") or {}
                web_image = images.get("web") or {}
                img_url = web_image.get("url")
                
                if not img_url:
                    continue

                # Extract image dimensions
                img_width = web_image.get("width")
                img_height = web_image.get("height")
                department_value = item.get("department") or ""

                # Fallback department filtering when canonical mapping expands to >1 CMA departments.
                if dept_filter_values:
                    dept_match = any(
                        self.contains_case_insensitive(department_value, mapped_value)
                        for mapped_value in dept_filter_values
                    )
                    if not dept_match:
                        dept_filtered += 1
                        continue

                culture_value = self.normalize_text(item.get("culture"))

                if filters.medium:
                    medium_text = self.normalize_text(item.get("technique"))
                    class_text = self.normalize_text(item.get("type"))
                    combined_medium = " ".join(
                        [medium_text, class_text, department_value]
                    ).strip()
                    medium_keywords = self.MEDIUM_KEYWORDS.get(filters.medium, [filters.medium])
                    medium_match = any(
                        self.contains_case_insensitive(combined_medium, keyword)
                        for keyword in medium_keywords
                    )
                    if not medium_match:
                        medium_filtered += 1
                        continue

                # Apply orientation filter (client-side)
                if filters.orientation and filters.orientation != "Any":
                    if not self.check_orientation(img_width, img_height, filters.orientation):
                        orientation_filtered += 1
                        continue
                
                # Apply resolution filter (client-side)
                if not self.check_resolution(
                    img_width, img_height, filters.min_width, filters.min_height
                ):
                    resolution_filtered += 1
                    continue
                
                # Extract artist info
                creators = item.get("creators") or []
                if creators:
                    artist = self.normalize_text(creators[0].get("description")) or "Unknown"
                elif item.get("culture"):
                    culture = item.get("culture")
                    if isinstance(culture, list):
                        artist = self.normalize_text(culture[0]) if culture else "Unknown"
                    else:
                        artist = self.normalize_text(culture) or "Unknown"
                else:
                    artist = "Unknown"
                
                # Extract artwork data
                title = item.get("title") or "Untitled"
                artwork_id = str(item.get("id", ""))
                share_license_status = self.normalize_text(item.get("share_license_status"))
                normalized_license = share_license_status.lower()
                is_downloadable = bool(img_url)
                open_markers = [
                    "open access",
                    "public domain",
                    "cc0",
                    "creative commons",
                    "no known copyright restrictions",
                ]
                restricted_markers = [
                    "restricted",
                    "rights reserved",
                    "permission required",
                    "copyrighted",
                ]
                if any(marker in normalized_license for marker in open_markers):
                    is_downloadable = True
                elif any(marker in normalized_license for marker in restricted_markers):
                    is_downloadable = False
                rights_label = share_license_status or self.default_rights_label(is_downloadable)
                
                # Create filename using base class method
                filename = self.create_filename(title, artwork_id, self.short_name)
                
                artwork = Artwork(
                    id=artwork_id,
                    source=self.short_name,
                    title=title,
                    artist=artist,
                    image_url=img_url,
                    filename=filename,
                    date=item.get("creation_date") or "",
                    medium=item.get("technique") or "",
                    department=department_value,
                    classification=item.get("type") or "",
                    credit=item.get("creditline") or "",
                    culture=culture_value,
                    is_downloadable=is_downloadable,
                    rights_label=rights_label,
                    dimensions=item.get("dimensions") or "",
                    description=item.get("description") or "",
                    accession_number=item.get("accession_number") or "",
                    image_width=img_width,
                    image_height=img_height,
                    metadata={
                        "tombstone": item.get("tombstone") or "",
                        "did_you_know": item.get("did_you_know") or "",
                        "share_license_status": share_license_status,
                    },
                )
                
                artworks.append(artwork)
                    
            except (KeyError, TypeError, ValueError) as e:
                self._log_warning(f"Failed to parse artwork {item.get('id')}: {e}")
                continue
        
        # Log filtering stats
        if dept_filtered > 0:
            self._log_info(f"Filtered out {dept_filtered} artworks by department")
        if medium_filtered > 0:
            self._log_info(f"Filtered out {medium_filtered} artworks by medium")

        if orientation_filtered > 0:
            self._log_info(f"Filtered out {orientation_filtered} artworks by orientation")
            result.filter_status.applied["orientation"] = (
                f"{filters.orientation} (filtered {orientation_filtered})"
            )
        
        if resolution_filtered > 0:
            self._log_info(f"Filtered out {resolution_filtered} artworks by resolution")
            result.filter_status.applied["resolution"] = (
                f"Min {filters.min_width}x{filters.min_height} (filtered {resolution_filtered})"
            )

        # Randomize final ordering per request for better variety before truncation.
        seed = filters.random_seed if filters.random_seed is not None else secrets.randbelow(2_147_483_647)
        random.Random(seed ^ 0xC0A).shuffle(artworks)
        if len(artworks) > filters.limit:
            artworks = artworks[:filters.limit]
        
        return artworks
    
    def get_departments(self) -> list[str]:
        """Return CMA-specific department list."""
        return CMA_DEPARTMENTS.copy()
