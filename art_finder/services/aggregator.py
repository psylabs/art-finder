"""Merge search results across multiple museum adapters."""

from __future__ import annotations

from dataclasses import replace
import random
import secrets
from typing import Callable

from ..adapters import get_adapter, get_adapter_names
from ..models import AdapterResult, SearchFilters


LogCallback = Callable[[str, str], None]


def _merge_filter_status(merged: AdapterResult, source: str, source_result: AdapterResult) -> None:
    """Merge source filter feedback with namespaced keys to avoid collisions."""
    for key, description in source_result.filter_status.applied.items():
        merged.filter_status.applied[f"{source}.{key}"] = description
    for key, reason in source_result.filter_status.skipped.items():
        merged.filter_status.skipped[f"{source}.{key}"] = reason


def _select_sources(filters: SearchFilters) -> tuple[list[str], list[str]]:
    """Return (valid_sources, invalid_sources) preserving request order."""
    available = get_adapter_names()
    available_keys = set(available.keys())

    requested = filters.sources or list(available.keys())
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in requested:
        source = str(raw).strip().upper()
        if not source or source in seen:
            continue
        seen.add(source)
        normalized.append(source)

    valid = [source for source in normalized if source in available_keys]
    invalid = [source for source in normalized if source not in available_keys]

    # Backward-compatible fallback if caller did not pass valid source codes.
    if not valid:
        valid = list(available.keys())

    return valid, invalid


def _resolve_seed(filters: SearchFilters) -> int:
    """Use caller-provided seed or generate one for non-deterministic runs."""
    if filters.random_seed is not None:
        return filters.random_seed
    return secrets.randbelow(2_147_483_647)


def search(filters: SearchFilters, log_callback: LogCallback | None = None) -> AdapterResult:
    """
    Search selected sources, merge results, then shuffle deterministically by seed.

    Returned `AdapterResult.seed_used` always stores the seed used for merge ordering.
    """
    merged = AdapterResult()
    sources, invalid_sources = _select_sources(filters)

    if invalid_sources:
        merged.warnings.append(
            f"Ignored unknown sources: {', '.join(sorted(invalid_sources))}"
        )

    if not sources:
        merged.errors.append("No museum sources available.")
        return merged

    for source in sources:
        try:
            adapter = get_adapter(source)
        except ValueError as exc:
            merged.errors.append(str(exc))
            merged.source_counts[source] = 0
            continue

        if log_callback:
            adapter.set_logger(log_callback)

        source_filters = replace(filters, sources=[source])
        source_result = adapter.search(source_filters)

        merged.artworks.extend(source_result.artworks)
        merged.source_counts[source] = len(source_result.artworks)
        _merge_filter_status(merged, source, source_result)

        for warning in source_result.warnings:
            merged.warnings.append(f"[{source}] {warning}")
        for error in source_result.errors:
            merged.errors.append(f"[{source}] {error}")

    if not merged.artworks:
        return merged

    seed = _resolve_seed(filters)
    merged.seed_used = seed
    random.Random(seed).shuffle(merged.artworks)

    if filters.random_seed is None:
        merged.filter_status.applied["random_seed"] = f"Auto-random seed: {seed}"
    else:
        merged.filter_status.applied["random_seed"] = f"Deterministic seed: {seed}"

    return merged
