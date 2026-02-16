"""Museum of Modern Art (MoMA) adapter."""

from __future__ import annotations

import csv
import io
import random
import re
from typing import Any

import requests

from . import register
from .base import MuseumAdapter
from ..mappings.departments import map_to_museum
from ..models import AdapterResult, Artwork, SearchFilters


@register
class MOMAAdapter(MuseumAdapter):
    """Adapter for the MoMA public collection dataset."""

    name = "Museum of Modern Art"
    short_name = "MOMA"
    base_url = "https://media.githubusercontent.com/media/MuseumofModernArt/collection/main/Artworks.csv"
    fetch_timeout = 90

    MEDIUM_KEYWORDS: dict[str, list[str]] = {
        "Decorative Arts": ["decorative", "design", "furniture", "applied"],
        "Drawings": ["drawing"],
        "Painting": ["painting"],
        "Photography": ["photograph", "photo"],
        "Prints": ["print", "etching", "lithograph", "woodcut"],
        "Sculpture": ["sculpture", "statue", "bronze", "marble"],
        "Textiles": ["textile", "fabric", "tapestry"],
    }

    _dataset_cache: list[dict[str, str]] | None = None
    _departments_cache: list[str] | None = None

    @staticmethod
    def _first(row: dict[str, str], *keys: str) -> str:
        """Return the first non-empty value for any candidate key."""
        for key in keys:
            value = row.get(key, "")
            if value:
                return value
        return ""

    @staticmethod
    def _parse_year(raw: str) -> int | None:
        """Parse year-like values from dataset columns."""
        value = raw.strip()
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            match = re.search(r"-?\d{1,4}", value)
            if not match:
                return None
            try:
                return int(match.group(0))
            except ValueError:
                return None

    @staticmethod
    def _parse_dimension_cm(raw: str) -> int | None:
        """Parse width/height numeric values in centimeters."""
        value = raw.strip()
        if not value:
            return None
        try:
            return int(round(float(value)))
        except ValueError:
            return None

    @classmethod
    def _dataset_rows(cls, ssl_bypass: bool) -> list[dict[str, str]]:
        """Load and cache MoMA dataset rows."""
        if cls._dataset_cache is not None:
            return cls._dataset_cache

        response = requests.get(
            cls.base_url,
            timeout=cls.fetch_timeout,
            verify=not ssl_bypass,
        )
        response.raise_for_status()

        text = response.content.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        rows: list[dict[str, str]] = []
        departments: set[str] = set()

        for row in reader:
            normalized = {
                "object_id": cls._first(row, "ObjectID", "Object ID"),
                "title": cls._first(row, "\ufeffTitle", "Title"),
                "artist": cls._first(row, "Artist", "ArtistDisplayName"),
                "artist_bio": cls._first(row, "ArtistBio", "Artist Bio"),
                "nationality": cls._first(row, "Nationality"),
                "date_display": cls._first(row, "Date"),
                "begin_date": cls._first(row, "BeginDate", "Begin Date"),
                "end_date": cls._first(row, "EndDate", "End Date"),
                "medium": cls._first(row, "Medium"),
                "classification": cls._first(row, "Classification"),
                "department": cls._first(row, "Department"),
                "credit_line": cls._first(row, "CreditLine", "Credit Line"),
                "accession": cls._first(row, "AccessionNumber", "Accession Number"),
                "dimensions": cls._first(row, "Dimensions"),
                "description": cls._first(row, "DateAcquired", "Date Acquired"),
                "url": cls._first(row, "URL"),
                "image_url": cls._first(row, "ImageURL", "Image URL"),
                "width_cm": cls._first(row, "Width (cm)", "Width(cm)"),
                "height_cm": cls._first(row, "Height (cm)", "Height(cm)"),
            }
            if normalized["department"]:
                departments.add(normalized["department"])
            rows.append(normalized)

        cls._dataset_cache = rows
        cls._departments_cache = sorted(departments)
        return rows

    def _do_search(self, filters: SearchFilters, result: AdapterResult) -> list[Artwork]:
        """Search MoMA dataset client-side using normalized filters."""
        self._log_info(
            f"Loading MoMA dataset (ssl_bypass={filters.ssl_bypass}, limit={filters.limit})"
        )
        rows = self._dataset_rows(filters.ssl_bypass)
        self._log_info(f"Dataset loaded: {len(rows)} rows")

        if filters.department:
            result.filter_status.applied["department"] = f"Genre: {filters.department} (mapped)"
        if filters.medium:
            result.filter_status.applied["medium"] = f"Medium: {filters.medium} (client-side)"
        if filters.place_of_origin:
            result.filter_status.applied["place_of_origin"] = (
                f"Place of origin contains: {filters.place_of_origin} (client-side)"
            )
        if filters.query:
            result.filter_status.applied["query"] = f"Search term: {filters.query}"

        if filters.min_width or filters.min_height:
            result.filter_status.skipped["resolution"] = (
                "MoMA dataset does not provide pixel dimensions; resolution filter skipped"
            )

        implicit_year_from = None
        if filters.department == "Modern Art" and filters.year_from is None:
            implicit_year_from = 1860
            result.filter_status.applied["modern_year_guard"] = (
                "Modern Art defaulted to year >= 1860 (override with Date Range)."
            )

        genre_filtered = 0
        medium_filtered = 0
        origin_filtered = 0
        query_filtered = 0
        year_filtered = 0
        orientation_filtered = 0
        no_image = 0

        artworks: list[Artwork] = []
        rows_to_scan = list(rows)
        random.Random(filters.random_seed).shuffle(rows_to_scan)

        for row in rows_to_scan:
            title = row["title"] or "Untitled"
            artist = row["artist"] or "Unknown"
            department = row["department"]
            classification = row["classification"]
            medium = row["medium"]
            nationality = row["nationality"]
            artist_bio = row["artist_bio"]

            place_of_origin = self.normalize_place_of_origin(
                nationality,
                fallback=artist_bio,
            )

            haystack = " ".join(
                [title, artist, department, classification, medium, nationality, artist_bio]
            ).lower()

            if filters.query and not self.contains_case_insensitive(haystack, filters.query):
                query_filtered += 1
                continue

            if filters.department:
                mapped = map_to_museum(filters.department, "moma")
                keywords = mapped if isinstance(mapped, list) else [mapped or filters.department]
                genre_match = any(
                    self.contains_case_insensitive(haystack, keyword or "")
                    for keyword in keywords
                )
                if not genre_match:
                    genre_filtered += 1
                    continue

            if filters.medium:
                medium_keywords = self.MEDIUM_KEYWORDS.get(filters.medium, [filters.medium])
                medium_haystack = " ".join([medium, classification, department]).lower()
                medium_match = any(
                    self.contains_case_insensitive(medium_haystack, keyword)
                    for keyword in medium_keywords
                )
                if not medium_match:
                    medium_filtered += 1
                    continue

            if filters.place_of_origin and not self.contains_case_insensitive(
                place_of_origin, filters.place_of_origin
            ):
                origin_filtered += 1
                continue

            begin_year = self._parse_year(row["begin_date"])
            end_year = self._parse_year(row["end_date"])
            year_from = filters.year_from if filters.year_from is not None else implicit_year_from
            year_to = filters.year_to
            if year_from or year_to:
                if year_from is not None and end_year is not None and end_year < year_from:
                    year_filtered += 1
                    continue
                if year_to is not None and begin_year is not None and begin_year > year_to:
                    year_filtered += 1
                    continue

            width_cm = self._parse_dimension_cm(row["width_cm"])
            height_cm = self._parse_dimension_cm(row["height_cm"])
            if filters.orientation and filters.orientation != "Any":
                if not self.check_orientation(width_cm, height_cm, filters.orientation):
                    orientation_filtered += 1
                    continue

            image_url = row["image_url"].strip()
            if not image_url:
                no_image += 1
                continue

            object_id = row["object_id"] or f"moma-{len(artworks)}"
            rights_label = "MoMA collection image URL from dataset (rights may vary)."

            artwork = Artwork(
                id=object_id,
                source=self.short_name,
                title=title,
                artist=artist,
                image_url=image_url,
                filename=self.create_filename(title, object_id, self.short_name),
                date=row["date_display"],
                medium=medium,
                department=department,
                classification=classification,
                credit=row["credit_line"],
                culture=nationality,
                place_of_origin=place_of_origin,
                dimensions=row["dimensions"],
                description=row["description"],
                accession_number=row["accession"],
                image_width=width_cm,
                image_height=height_cm,
                is_downloadable=True,
                rights_label=rights_label,
                metadata={
                    "url": row["url"],
                    "artist_bio": artist_bio,
                },
            )
            artworks.append(artwork)

            if len(artworks) >= filters.limit:
                break

        if genre_filtered > 0:
            self._log_info(f"Filtered out {genre_filtered} rows by genre mapping")
        if medium_filtered > 0:
            self._log_info(f"Filtered out {medium_filtered} rows by medium")
        if origin_filtered > 0:
            self._log_info(f"Filtered out {origin_filtered} rows by place of origin")
        if query_filtered > 0:
            self._log_info(f"Filtered out {query_filtered} rows by query")
        if year_filtered > 0:
            self._log_info(f"Filtered out {year_filtered} rows by year range")
        if orientation_filtered > 0:
            self._log_info(f"Filtered out {orientation_filtered} rows by orientation")
        if no_image > 0:
            self._log_info(f"Skipped {no_image} rows without image URLs")

        return artworks

    def get_departments(self) -> list[str]:
        """Return MoMA native department list discovered from dataset."""
        if self._departments_cache is None:
            return []
        return self._departments_cache.copy()
