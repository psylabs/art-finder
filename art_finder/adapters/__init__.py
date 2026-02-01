"""Museum adapter registry and utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import MuseumAdapter

# Registry of available adapters
_ADAPTERS: dict[str, type[MuseumAdapter]] = {}


def register(cls: type["MuseumAdapter"]) -> type["MuseumAdapter"]:
    """Decorator to register an adapter class."""
    _ADAPTERS[cls.short_name] = cls
    return cls


def get_adapter(short_name: str) -> "MuseumAdapter":
    """Get an adapter instance by short name (e.g., 'CMA', 'AIC')."""
    if short_name not in _ADAPTERS:
        available = ", ".join(_ADAPTERS.keys()) or "none"
        raise ValueError(f"Unknown adapter: {short_name}. Available: {available}")
    return _ADAPTERS[short_name]()


def list_adapters() -> list[tuple[str, str]]:
    """Return list of (short_name, full_name) tuples for all registered adapters."""
    return [(name, cls.name) for name, cls in _ADAPTERS.items()]


def get_adapter_names() -> dict[str, str]:
    """Return dict mapping short_name -> full_name."""
    return {name: cls.name for name, cls in _ADAPTERS.items()}


# Import adapters to trigger registration
# These imports must come after the registry is defined
from . import cma  # noqa: E402, F401
from . import aic  # noqa: E402, F401
