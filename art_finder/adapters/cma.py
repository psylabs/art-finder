"""Cleveland Museum of Art adapter."""

from __future__ import annotations

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
    
    def _do_search(self, filters: SearchFilters, result: AdapterResult) -> list[Artwork]:
        """Execute search against CMA API."""
        # Build API params
        params = {
            "has_image": 1,
            "limit": filters.limit,
        }
        
        # Apply date filters if provided
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
                # CMA API expects single department string
                if isinstance(cma_dept, list):
                    # For multiple mappings, use the first one
                    params["department"] = cma_dept[0]
                    result.filter_status.applied["department"] = f"Department: {cma_dept[0]}"
                else:
                    params["department"] = cma_dept
                    result.filter_status.applied["department"] = f"Department: {cma_dept}"
            else:
                result.filter_status.skipped["department"] = (
                    f"No CMA mapping for '{filters.department}'"
                )
        
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
                    artist = creators[0].get("description", "Unknown")
                elif item.get("culture"):
                    culture = item.get("culture")
                    if isinstance(culture, list):
                        artist = culture[0] if culture else "Unknown"
                    else:
                        artist = culture or "Unknown"
                else:
                    artist = "Unknown"
                
                # Extract artwork data
                title = item.get("title") or "Untitled"
                artwork_id = str(item.get("id", ""))
                
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
                    department=item.get("department") or "",
                    classification=item.get("type") or "",
                    credit=item.get("creditline") or "",
                    culture=str(item.get("culture") or ""),
                    dimensions=item.get("dimensions") or "",
                    description=item.get("description") or "",
                    accession_number=item.get("accession_number") or "",
                    image_width=img_width,
                    image_height=img_height,
                    metadata={
                        "tombstone": item.get("tombstone") or "",
                        "did_you_know": item.get("did_you_know") or "",
                        "share_license_status": item.get("share_license_status") or "",
                    },
                )
                
                artworks.append(artwork)
                
                # Stop if we have enough
                if len(artworks) >= filters.limit:
                    break
                    
            except (KeyError, TypeError, ValueError) as e:
                self._log_warning(f"Failed to parse artwork {item.get('id')}: {e}")
                continue
        
        # Log filtering stats
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
        
        return artworks
    
    def get_departments(self) -> list[str]:
        """Return CMA-specific department list."""
        return CMA_DEPARTMENTS.copy()
