"""Art Institute of Chicago adapter."""

from __future__ import annotations

import requests

from . import register
from .base import MuseumAdapter
from ..models import Artwork, SearchFilters, AdapterResult
from ..mappings.departments import map_to_museum


@register
class AICAdapter(MuseumAdapter):
    """Adapter for Art Institute of Chicago API."""
    
    name = "Art Institute of Chicago"
    short_name = "AIC"
    base_url = "https://api.artic.edu/api/v1/artworks/search"
    
    DEFAULT_IIIF_URL = "https://www.artic.edu/iiif/2"
    
    def __init__(self) -> None:
        self._discovered_departments: set[str] = set()
    
    def _do_search(self, filters: SearchFilters, result: AdapterResult) -> list[Artwork]:
        """Execute search against AIC API and return artworks."""
        # Build fields list
        fields = ",".join([
            "id",
            "title",
            "artist_display",
            "date_display",
            "date_start",
            "date_end",
            "medium_display",
            "department_title",
            "classification_title",
            "credit_line",
            "image_id",
            "thumbnail",
            "place_of_origin",
            "accession_number",
        ])
        
        params: dict[str, str | int] = {
            "fields": fields,
            "limit": filters.limit,
        }
        
        # Add search query
        if filters.query:
            params["q"] = filters.query
            result.filter_status.applied["query"] = f"Search term: {filters.query}"
        
        # Note: AIC doesn't support year range in simple params - will filter client-side
        if filters.year_from or filters.year_to:
            result.filter_status.skipped["year_range"] = (
                "AIC API doesn't support year range filtering; applied client-side"
            )
        
        # Note: AIC doesn't support department filtering in API - will filter client-side
        museum_dept = None
        if filters.department:
            museum_dept = map_to_museum(filters.department, "aic")
            if museum_dept:
                result.filter_status.applied["department"] = (
                    f"Department filter: {filters.department} (client-side)"
                )
            else:
                result.filter_status.skipped["department"] = (
                    f"No AIC mapping for department: {filters.department}"
                )
        
        self._log_info(
            f"Fetching from API (timeout={self.fetch_timeout}s, "
            f"ssl_bypass={filters.ssl_bypass}, limit={filters.limit})"
        )
        
        response = requests.get(
            self.base_url,
            params=params,
            timeout=self.fetch_timeout,
            verify=not filters.ssl_bypass,
        )
        response.raise_for_status()
        
        data = response.json()
        iiif_url = data.get("config", {}).get("iiif_url", self.DEFAULT_IIIF_URL)
        raw_artworks = data.get("data", [])
        
        self._log_info(f"Received {len(raw_artworks)} artworks from API")
        
        # Track filtering stats
        year_filtered = 0
        dept_filtered = 0
        orientation_filtered = 0
        resolution_filtered = 0
        no_image = 0
        
        artworks: list[Artwork] = []
        
        for item in raw_artworks:
            try:
                # Track department for discovery
                dept_title = item.get("department_title", "")
                if dept_title:
                    self._discovered_departments.add(dept_title)
                
                # Filter by department (client-side)
                if museum_dept:
                    if isinstance(museum_dept, list):
                        if dept_title not in museum_dept:
                            dept_filtered += 1
                            continue
                    elif dept_title != museum_dept:
                        dept_filtered += 1
                        continue
                
                # Filter by year range (client-side)
                if filters.year_from or filters.year_to:
                    date_start = item.get("date_start")
                    date_end = item.get("date_end")
                    
                    # Use date_end for year_from check, date_start for year_to check
                    # This catches artworks that span the requested range
                    if filters.year_from and date_end is not None:
                        if date_end < filters.year_from:
                            year_filtered += 1
                            continue
                    if filters.year_to and date_start is not None:
                        if date_start > filters.year_to:
                            year_filtered += 1
                            continue
                
                # Must have an image
                image_id = item.get("image_id")
                if not image_id:
                    no_image += 1
                    continue
                
                image_url = f"{iiif_url}/{image_id}/full/843,/0/default.jpg"
                
                # Get thumbnail dimensions for orientation/resolution checks
                thumb = item.get("thumbnail") or {}
                width = thumb.get("width")
                height = thumb.get("height")
                
                # Filter by orientation
                if filters.orientation:
                    if not self.check_orientation(width, height, filters.orientation):
                        orientation_filtered += 1
                        continue
                    result.filter_status.applied["orientation"] = (
                        f"Orientation: {filters.orientation}"
                    )
                
                # Filter by resolution
                if filters.min_width or filters.min_height:
                    if not self.check_resolution(width, height, filters.min_width, filters.min_height):
                        resolution_filtered += 1
                        continue
                    result.filter_status.applied["resolution"] = (
                        f"Min resolution: {filters.min_width or 'any'}x{filters.min_height or 'any'}"
                    )
                
                # Build artwork object
                title = item.get("title", "Untitled")
                artwork_id = str(item.get("id", ""))
                
                artwork = Artwork(
                    id=artwork_id,
                    source=self.short_name,
                    title=title,
                    artist=item.get("artist_display", "Unknown"),
                    image_url=image_url,
                    filename=self.create_filename(title, artwork_id, self.short_name),
                    date=item.get("date_display", ""),
                    medium=item.get("medium_display", ""),
                    department=dept_title,
                    classification=item.get("classification_title", ""),
                    credit=item.get("credit_line", ""),
                    culture=item.get("place_of_origin", ""),
                    description=thumb.get("alt_text", ""),
                    accession_number=item.get("accession_number", ""),
                    image_width=width,
                    image_height=height,
                )
                
                artworks.append(artwork)
                
                # Stop if we've reached the limit
                if len(artworks) >= filters.limit:
                    break
                    
            except (KeyError, TypeError, ValueError) as e:
                self._log_warning(f"Failed to parse artwork {item.get('id')}: {e}")
                continue
        
        # Log filtering summary
        if year_filtered > 0:
            self._log_info(f"Filtered {year_filtered} artworks by year range")
        if dept_filtered > 0:
            self._log_info(f"Filtered {dept_filtered} artworks by department")
        if orientation_filtered > 0:
            self._log_info(f"Filtered {orientation_filtered} artworks by orientation")
        if resolution_filtered > 0:
            self._log_info(f"Filtered {resolution_filtered} artworks by resolution")
        if no_image > 0:
            self._log_info(f"Skipped {no_image} artworks without images")
        
        return artworks
    
    def get_departments(self) -> list[str]:
        """Return dynamically discovered departments from previous searches."""
        return sorted(self._discovered_departments)
