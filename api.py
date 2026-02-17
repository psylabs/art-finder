"""FastAPI backend for the React migration of Art Findr."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from art_finder.adapters import get_adapter_names
from art_finder.mappings import get_canonical_genres, get_canonical_media
from art_finder.mappings.departments import DEPARTMENT_MAP
from art_finder.mappings.field_enums import MEDIUM_KEYWORD_MAP, MUSEUM_FIELD_MAP
from art_finder.models import SearchFilters
from art_finder.services import search as search_aggregated

FETCH_TIMEOUT = 30
IMAGE_TIMEOUT = 30
DEFAULT_FETCH_LIMIT = 50
FETCH_LIMIT_OPTIONS = [50, 100, 200, 500, 1000]
ALL_GENRES_LABEL = "All genres"
ALL_MEDIA_LABEL = "All media"
WEB_DIST_DIR = (Path(__file__).resolve().parent / "web" / "dist").resolve()
WEB_ASSETS_DIR = WEB_DIST_DIR / "assets"

app = FastAPI(title="Art Findr API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if WEB_ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=WEB_ASSETS_DIR), name="assets")


class SearchRequest(BaseModel):
    """Payload sent by the React app."""

    sources: list[str] = Field(default_factory=list)
    query: str | None = None
    year_from: int | None = None
    year_to: int | None = None
    department: str | None = None
    medium: str | None = None
    orientation: str = "Any"
    limit: int = DEFAULT_FETCH_LIMIT
    use_random_seed: bool = False
    random_seed: int | None = None
    ssl_bypass: bool = False


def _normalize_sources(sources: list[str]) -> list[str]:
    adapter_names = get_adapter_names()
    available = set(adapter_names.keys())
    normalized: list[str] = []
    seen: set[str] = set()
    for source in sources:
        code = source.strip().upper()
        if code and code in available and code not in seen:
            normalized.append(code)
            seen.add(code)
    return normalized or list(adapter_names.keys())


def _normalize_orientation(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if normalized in {"portrait", "landscape"}:
        return normalized.title()
    return None


def _download_image(image_url: str, ssl_bypass: bool) -> tuple[bytes, str]:
    parsed = urlparse(image_url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="Image URL must be http/https.")

    referer = f"{parsed.scheme}://{parsed.netloc}/" if parsed.netloc else ""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    if referer:
        headers["Referer"] = referer

    try:
        response = requests.get(
            image_url,
            timeout=IMAGE_TIMEOUT,
            verify=not ssl_bypass,
            headers=headers,
        )
        if response.status_code == 403 and "moma.org" in (parsed.netloc or ""):
            headers["Referer"] = "https://www.moma.org/"
            response = requests.get(
                image_url,
                timeout=IMAGE_TIMEOUT,
                verify=not ssl_bypass,
                headers=headers,
            )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Image download failed: {exc}") from exc

    mime_type = response.headers.get("content-type", "application/octet-stream")
    mime_type = mime_type.split(";")[0].strip() or "application/octet-stream"
    return response.content, mime_type


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/options")
def options() -> dict[str, Any]:
    return {
        "source_names": get_adapter_names(),
        "genre_options": [ALL_GENRES_LABEL, *get_canonical_genres()],
        "medium_options": [ALL_MEDIA_LABEL, *get_canonical_media()],
        "fetch_limit_options": FETCH_LIMIT_OPTIONS,
        "defaults": {
            "sources": list(get_adapter_names().keys()),
            "orientation": "Portrait",
            "limit": DEFAULT_FETCH_LIMIT,
            "use_random_seed": False,
            "random_seed": 42,
            "ssl_bypass": False,
        },
    }


@app.get("/api/help/mappings")
def help_mappings() -> dict[str, Any]:
    return {
        "genres": get_canonical_genres(),
        "media": get_canonical_media(),
        "department_map": DEPARTMENT_MAP,
        "museum_field_map": MUSEUM_FIELD_MAP,
        "medium_keyword_map": MEDIUM_KEYWORD_MAP,
    }


@app.post("/api/search")
def search_artworks(payload: SearchRequest) -> dict[str, Any]:
    logs: list[str] = []

    def _log(level: str, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logs.append(f"{timestamp} | {level:<5} | {message}")

    sources = _normalize_sources(payload.sources)
    query = payload.query.strip() if payload.query else None
    query = query if query else None
    random_seed = payload.random_seed if payload.use_random_seed else None
    department = payload.department
    if department == ALL_GENRES_LABEL:
        department = None
    medium = payload.medium
    if medium == ALL_MEDIA_LABEL:
        medium = None

    filters = SearchFilters(
        sources=sources,
        query=query,
        year_from=payload.year_from,
        year_to=payload.year_to,
        department=department,
        medium=medium,
        orientation=_normalize_orientation(payload.orientation),
        has_image=True,
        limit=max(1, min(payload.limit, 1000)),
        random_seed=random_seed,
        ssl_bypass=payload.ssl_bypass,
    )

    _log("INFO", f"Fetching from sources: {', '.join(sources)}")
    result = search_aggregated(filters, log_callback=_log)
    return {
        "artworks": [artwork.to_dict() for artwork in result.artworks],
        "errors": result.errors,
        "warnings": result.warnings,
        "filter_status": {
            "applied": result.filter_status.applied,
            "skipped": result.filter_status.skipped,
        },
        "source_counts": result.source_counts,
        "seed_used": result.seed_used,
        "logs": logs[-200:],
    }


@app.get("/api/download")
def download(
    url: str = Query(..., description="Image URL"),
    filename: str = Query("artwork.jpg", description="Suggested filename"),
    ssl_bypass: bool = Query(False, description="Disable SSL verification"),
) -> Response:
    image_bytes, mime_type = _download_image(url, ssl_bypass=ssl_bypass)
    return Response(
        content=image_bytes,
        media_type=mime_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def serve() -> None:
    """Convenience launcher for local development."""
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str) -> FileResponse:
    """Serve the built React app when deployed as a single container."""
    if full_path.startswith("api"):
        raise HTTPException(status_code=404, detail="Not found")

    if not WEB_DIST_DIR.exists():
        raise HTTPException(status_code=404, detail="Frontend assets are not built.")

    # Serve static files directly when they exist, otherwise hand off to index.html.
    if full_path:
        candidate = (WEB_DIST_DIR / full_path).resolve()
        if candidate.is_file() and WEB_DIST_DIR in candidate.parents:
            return FileResponse(candidate)

    return FileResponse(WEB_DIST_DIR / "index.html")


if __name__ == "__main__":
    serve()
