"""Abstract base class for museum adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable
import requests

from ..models import Artwork, SearchFilters, AdapterResult, FilterStatus


class MuseumAdapter(ABC):
    """
    Abstract base class for museum API adapters.
    
    Subclasses implement museum-specific API logic while this base class
    provides common error handling and logging infrastructure.
    """
    
    # Subclasses must define these
    name: str = "Unknown Museum"  # Full display name
    short_name: str = "UNK"  # Short identifier (e.g., "CMA", "AIC")
    base_url: str = ""
    
    # Timeouts (can be overridden)
    fetch_timeout: int = 30
    image_timeout: int = 5
    
    # Logging callback - set by app to integrate with UI logging
    _log_callback: Callable[[str, str], None] | None = None
    
    def set_logger(self, callback: Callable[[str, str], None]) -> None:
        """Set logging callback. Signature: callback(level, message)."""
        self._log_callback = callback
    
    def _log(self, level: str, message: str) -> None:
        """Log a message if callback is set."""
        if self._log_callback:
            self._log_callback(level, f"[{self.short_name}] {message}")
    
    def _log_info(self, message: str) -> None:
        self._log("INFO", message)
    
    def _log_warning(self, message: str) -> None:
        self._log("WARN", message)
    
    def _log_error(self, message: str) -> None:
        self._log("ERROR", message)
    
    def search(self, filters: SearchFilters) -> AdapterResult:
        """
        Search for artworks with the given filters.
        
        This method wraps _do_search with error handling to ensure
        we always return an AdapterResult, never raise exceptions.
        """
        result = AdapterResult(
            artworks=[],
            errors=[],
            warnings=[],
            filter_status=FilterStatus(),
        )
        
        try:
            self._log_info(f"Search started (limit={filters.limit})")
            result.artworks = self._do_search(filters, result)
            self._log_info(f"Search complete: {len(result.artworks)} artworks found")
            
        except requests.Timeout:
            msg = f"{self.name} took too long to respond. Try again or reduce the limit."
            result.errors.append(msg)
            self._log_error(f"Timeout after {self.fetch_timeout}s")
            
        except requests.ConnectionError:
            msg = f"Could not connect to {self.name}. Check your internet connection."
            result.errors.append(msg)
            self._log_error("Connection failed")
            
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else "unknown"
            msg = f"{self.name} returned an error (status {status}). Try again later."
            result.errors.append(msg)
            self._log_error(f"HTTP error: {status}")
            
        except requests.RequestException as e:
            msg = f"Error communicating with {self.name}. Try again."
            result.errors.append(msg)
            self._log_error(f"Request error: {e}")
            
        except Exception as e:
            msg = f"Unexpected error from {self.name}."
            result.errors.append(msg)
            self._log_error(f"Unexpected error: {type(e).__name__}: {e}")
        
        return result
    
    @abstractmethod
    def _do_search(self, filters: SearchFilters, result: AdapterResult) -> list[Artwork]:
        """
        Implement the actual search logic.
        
        Args:
            filters: Search filters to apply
            result: AdapterResult to update with warnings/filter_status
        
        Returns:
            List of Artwork objects
        
        Note: This method should update result.filter_status and result.warnings
              as it processes filters. Exceptions are caught by search().
        """
        pass
    
    @abstractmethod
    def get_departments(self) -> list[str]:
        """Return list of department names available for this museum."""
        pass
    
    def check_orientation(self, width: int | None, height: int | None, 
                          orientation: str) -> bool:
        """Check if dimensions match the requested orientation."""
        if width is None or height is None:
            return True  # Can't filter without dimensions
        
        is_portrait = height > width
        if orientation == "Portrait":
            return is_portrait
        elif orientation == "Landscape":
            return not is_portrait
        return True  # Unknown orientation, don't filter
    
    def check_resolution(self, width: int | None, height: int | None,
                         min_width: int | None, min_height: int | None) -> bool:
        """Check if dimensions meet minimum resolution requirements."""
        if min_width and width and width < min_width:
            return False
        if min_height and height and height < min_height:
            return False
        return True
    
    @staticmethod
    def create_filename(title: str, artwork_id: str, museum_abbrev: str) -> str:
        """Create a human-readable filename from title and ID."""
        filename_base = f"{museum_abbrev}-{title}"
        
        # Remove invalid filename characters
        invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
        for char in invalid_chars:
            filename_base = filename_base.replace(char, '')
        
        # Normalize whitespace
        filename_base = ' '.join(filename_base.split())
        
        # Limit length
        max_length = 100
        if len(filename_base) > max_length:
            filename_base = filename_base[:max_length].strip()
        
        return f"{filename_base}-{artwork_id}.jpg"
