"""Art Findr - Streamlit application."""

from datetime import date, datetime
import html
import re
import requests
import streamlit as st
from urllib.parse import urlparse

from art_finder.adapters import get_adapter_names
from art_finder.models import SearchFilters, AdapterResult
from art_finder.mappings import get_canonical_genres, get_canonical_media
from art_finder.services import search as search_aggregated

# Configuration
FETCH_TIMEOUT = 30
IMAGE_TIMEOUT = 30
DEFAULT_FETCH_LIMIT = 50
FETCH_LIMIT_OPTIONS = [50, 100, 200, 500, 1000]
ALL_GENRES_LABEL = "All genres"
ALL_MEDIA_LABEL = "All media"
MIN_FILTER_DATE = date(1, 1, 1)
MAX_FILTER_DATE = date(2100, 12, 31)
MUSEUM_LOGOS = {
    "AIC": "https://upload.wikimedia.org/wikipedia/commons/3/32/Art_Institute_of_Chicago_logo.svg",
    "CMA": "https://upload.wikimedia.org/wikipedia/commons/7/74/Logo_Cleveland_Museum_of_Art.svg",
    "MOMA": "https://upload.wikimedia.org/wikipedia/commons/2/21/Museum_of_Modern_Art_logo.svg",
}

st.set_page_config(page_title="Art Findr", layout="wide")

st.markdown(
    """
<style>
.art-image-frame {
    width: 100%;
    height: 68vh;
    min-height: 420px;
    max-height: 760px;
    border: 1px solid rgba(49, 51, 63, 0.2);
    border-radius: 12px;
    background: transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
}
.art-image-frame img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
}
.museum-source {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 0.5rem;
}
.museum-source img {
    height: 18px;
    max-width: 88px;
    width: auto;
    object-fit: contain;
}
.museum-source img.museum-logo-moma {
    height: 14px;
    max-width: 76px;
}
.museum-source .museum-source-name {
    font-size: 0.92rem;
}
</style>
""",
    unsafe_allow_html=True,
)


# =============================================================================
# Session State Initialization
# =============================================================================

def init_session_state():
    """Initialize all session state variables."""
    defaults = {
        "images": [],
        "current_idx": 0,
        "loaded": False,
        "debug_logs": [],
        "last_result": None,  # Store AdapterResult for filter feedback
        # Filters
        "selected_sources": ["MOMA", "CMA", "AIC"],
        "selected_sources_last": ["MOMA", "CMA", "AIC"],
        "orientation_filter": "Portrait",
        "orientation_filter_last": "Portrait",
        "department_filter": ALL_GENRES_LABEL,
        "department_filter_last": ALL_GENRES_LABEL,
        "medium_filter": ALL_MEDIA_LABEL,
        "medium_filter_last": ALL_MEDIA_LABEL,
        "place_origin_filter": "",
        "place_origin_filter_last": "",
        "fetch_limit": DEFAULT_FETCH_LIMIT,
        "fetch_limit_last": DEFAULT_FETCH_LIMIT,
        "use_random_seed": False,
        "use_random_seed_last": False,
        "random_seed_value": 42,
        "random_seed_value_last": 42,
        # New filters
        "year_from": None,
        "year_from_last": None,
        "year_to": None,
        "year_to_last": None,
        "year_from_date": None,
        "year_to_date": None,
        "search_term": "",
        "search_term_last": "",
        # Options
        "ssl_bypass": False,
        "ssl_bypass_last": False,
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


init_session_state()


# =============================================================================
# Logging
# =============================================================================

def _append_log(level: str, message: str):
    """Append a log entry to session state."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"{timestamp} | {level:<5} | {message}"
    st.session_state.debug_logs.append(entry)
    # Keep last 200 entries
    st.session_state.debug_logs = st.session_state.debug_logs[-200:]


def log_event(message: str):
    _append_log("INFO", message)


def log_warning(message: str):
    _append_log("WARN", message)


def log_error(message: str):
    _append_log("ERROR", message)


def adapter_log_callback(level: str, message: str):
    """Callback for adapters to log through our system."""
    _append_log(level, message)


# =============================================================================
# State Management
# =============================================================================

def reset_loaded_state(reason: str):
    """Reset loaded state when filters change."""
    log_event(f"Reload required: {reason}")
    st.session_state.images = []
    st.session_state.current_idx = 0
    st.session_state.loaded = False
    st.session_state.last_result = None


def check_filter_changes():
    """Check if any filters changed and reset state if needed."""
    changes = []

    selected_sources = list(st.session_state.selected_sources)
    sources_last = list(st.session_state.selected_sources_last)
    if sorted(selected_sources) != sorted(sources_last):
        changes.append("API selection changed")
        st.session_state.selected_sources_last = selected_sources
        st.session_state.department_filter = ALL_GENRES_LABEL

    # Check scalar filters.
    filter_checks = [
        ("orientation_filter", "orientation changed"),
        ("department_filter", "department changed"),
        ("medium_filter", "medium changed"),
        ("place_origin_filter", "place of origin changed"),
        ("fetch_limit", "fetch limit changed"),
        ("year_from", "year range changed"),
        ("year_to", "year range changed"),
        ("ssl_bypass", "SSL bypass changed"),
        ("use_random_seed", "seed mode changed"),
    ]

    for key, reason in filter_checks:
        last_key = f"{key}_last"
        if st.session_state.get(key) != st.session_state.get(last_key):
            changes.append(reason)
            st.session_state[last_key] = st.session_state[key]

    if st.session_state.use_random_seed:
        if st.session_state.random_seed_value != st.session_state.random_seed_value_last:
            changes.append("seed value changed")
            st.session_state.random_seed_value_last = st.session_state.random_seed_value

    if st.session_state.search_term != st.session_state.search_term_last:
        changes.append("search term changed")
        st.session_state.search_term_last = st.session_state.search_term

    # Reset if any changes
    if changes:
        # Deduplicate reasons
        unique_reasons = list(dict.fromkeys(changes))
        reset_loaded_state(", ".join(unique_reasons))


# =============================================================================
# Artwork Fetching
# =============================================================================

def fetch_artworks() -> AdapterResult:
    """Fetch artworks using the selected APIs and merge results."""
    selected_sources = list(st.session_state.selected_sources)
    query = st.session_state.search_term.strip() or None
    random_seed = (
        st.session_state.random_seed_value if st.session_state.use_random_seed else None
    )

    # Build filters
    filters = SearchFilters(
        sources=selected_sources,
        query=query,
        year_from=st.session_state.year_from,
        year_to=st.session_state.year_to,
        department=(
            None if st.session_state.department_filter == ALL_GENRES_LABEL
            else st.session_state.department_filter
        ),
        medium=(
            None if st.session_state.medium_filter == ALL_MEDIA_LABEL
            else st.session_state.medium_filter
        ),
        place_of_origin=st.session_state.place_origin_filter.strip() or None,
        orientation=st.session_state.orientation_filter,
        has_image=True,
        limit=st.session_state.fetch_limit,
        random_seed=random_seed,
        ssl_bypass=st.session_state.ssl_bypass,
    )

    log_event(f"Fetching from sources: {', '.join(selected_sources)}")

    # Execute search
    return search_aggregated(filters, log_callback=adapter_log_callback)


@st.cache_data(show_spinner=False, ttl=3600, max_entries=512)
def download_high_res(image_url: str, ssl_bypass: bool) -> tuple[bytes | None, str]:
    """Download high-resolution image."""
    try:
        parsed = urlparse(image_url)
        referer = f"{parsed.scheme}://{parsed.netloc}/" if parsed.scheme and parsed.netloc else ""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
            ),
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        }
        if referer:
            headers["Referer"] = referer
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
        mime_type = response.headers.get("content-type", "application/octet-stream")
        mime_type = mime_type.split(";")[0].strip() or "application/octet-stream"
        return response.content, mime_type
    except requests.exceptions.RequestException as e:
        log_error(f"Download failed: {e}")
        return None, ""


# =============================================================================
# UI Components
# =============================================================================

def render_filter_feedback(result: AdapterResult):
    """Render feedback about which filters were applied/skipped."""
    if not result:
        return
    
    status = result.filter_status

    def clean_description(description: str) -> str:
        """Strip implementation details from filter descriptions."""
        cleaned = re.sub(r"\s*\((?:client-side|mapped)\)\s*", "", description).strip()
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        return cleaned
    
    # Show applied filters
    if status.applied:
        with st.expander("✓ Filters Applied", expanded=False):
            deduped: dict[str, set[str]] = {}
            for name, description in status.applied.items():
                if "random_seed" in name:
                    continue
                source = name.split(".", 1)[0].upper() if "." in name else ""
                cleaned = clean_description(description)
                if not cleaned:
                    continue
                deduped.setdefault(cleaned, set())
                if source:
                    deduped[cleaned].add(source)

            for description, sources in deduped.items():
                if sources and len(sources) > 1:
                    st.caption(f"• {description} ({', '.join(sorted(sources))})")
                else:
                    st.caption(f"• {description}")
    
    # Show skipped filters (warnings)
    if status.skipped:
        with st.expander("⚠️ Filters Skipped", expanded=True):
            for name, reason in status.skipped.items():
                st.warning(reason)
    
    # Show warnings
    if result.warnings:
        for warning in result.warnings:
            st.warning(warning)

    if result.source_counts:
        with st.expander("Source Counts", expanded=False):
            adapter_names = get_adapter_names()
            for source, count in result.source_counts.items():
                source_label = adapter_names.get(source, source)
                st.caption(f"{source_label}: {count} artworks")


def render_errors(result: AdapterResult):
    """Render any errors from the adapter."""
    if not result or not result.errors:
        return
    
    for error in result.errors:
        st.error(error)


def get_department_options() -> list[str]:
    """Get canonical genre options shared across selected APIs."""
    return [ALL_GENRES_LABEL] + get_canonical_genres()


def get_medium_options() -> list[str]:
    """Get canonical medium options shared across selected APIs."""
    return [ALL_MEDIA_LABEL] + get_canonical_media()


def render_sidebar():
    """Render the sidebar with filters and debug console."""
    with st.sidebar:
        st.subheader("Filters")

        adapter_names = get_adapter_names()
        source_options = list(adapter_names.keys())

        selected_sources: list[str] = []
        with st.expander("Museum", expanded=False):
            for source in source_options:
                key = f"source_enabled_{source}"
                if key not in st.session_state:
                    st.session_state[key] = source in st.session_state.selected_sources
                checked = st.checkbox(f"{adapter_names[source]} ({source})", key=key)
                if checked:
                    selected_sources.append(source)

        if not selected_sources and source_options:
            fallback = source_options[0]
            st.session_state[f"source_enabled_{fallback}"] = True
            selected_sources = [fallback]
            st.warning("At least one museum must be selected.")
        st.session_state.selected_sources = selected_sources

        # Genre (first)
        dept_options = get_department_options()
        if st.session_state.department_filter not in dept_options:
            st.session_state.department_filter = ALL_GENRES_LABEL

        st.selectbox(
            "Genre",
            dept_options,
            key="department_filter",
            help=(
                "Canonical genres are normalized across museums. "
                "Each museum's native departments map to these shared options."
            ),
        )

        # Medium (second)
        medium_options = get_medium_options()
        if st.session_state.medium_filter not in medium_options:
            st.session_state.medium_filter = ALL_MEDIA_LABEL
        st.selectbox(
            "Medium",
            medium_options,
            key="medium_filter",
            help="Client-side medium normalization using each source's medium/classification fields.",
        )

        # Place of origin (third)
        st.text_input(
            "Place of origin contains",
            value=st.session_state.place_origin_filter,
            key="place_origin_filter",
            help="Substring match across normalized place-of-origin values.",
        )

        st.text_input(
            "Search term",
            value=st.session_state.search_term,
            key="search_term",
            help="Applied across all selected museums.",
        )

        # Orientation
        st.selectbox(
            "Orientation",
            ["Any", "Portrait", "Landscape"],
            key="orientation_filter"
        )

        # Year range
        st.markdown("**Date Range**")
        col1, col2 = st.columns(2)
        year_from_default = st.session_state.year_from_date
        if year_from_default is None and st.session_state.year_from:
            year_from_default = date(st.session_state.year_from, 1, 1)
        year_to_default = st.session_state.year_to_date
        if year_to_default is None and st.session_state.year_to:
            year_to_default = date(st.session_state.year_to, 12, 31)
        with col1:
            st.date_input(
                "From date",
                value=year_from_default,
                key="year_from_date",
                min_value=MIN_FILTER_DATE,
                max_value=MAX_FILTER_DATE,
                help="Earliest creation date (year is used for filtering).",
                format="YYYY-MM-DD",
            )
            if st.button("Clear", key="clear_from_date"):
                st.session_state.year_from_date = None
                st.session_state.year_from = None
                st.rerun()
            st.session_state.year_from = (
                st.session_state.year_from_date.year
                if st.session_state.year_from_date
                else None
            )
        with col2:
            st.date_input(
                "To date",
                value=year_to_default,
                key="year_to_date",
                min_value=MIN_FILTER_DATE,
                max_value=MAX_FILTER_DATE,
                help="Latest creation date (year is used for filtering).",
                format="YYYY-MM-DD",
            )
            if st.button("Clear", key="clear_to_date"):
                st.session_state.year_to_date = None
                st.session_state.year_to = None
                st.rerun()
            st.session_state.year_to = (
                st.session_state.year_to_date.year
                if st.session_state.year_to_date
                else None
            )

        st.caption("Filters apply when you click Load Artworks.")

        with st.expander("Advanced", expanded=False):
            st.selectbox(
                "Fetch limit",
                FETCH_LIMIT_OPTIONS,
                key="fetch_limit"
            )

            st.checkbox(
                "Bypass SSL verification",
                key="ssl_bypass",
                help="Use if you encounter SSL errors",
            )

            st.checkbox("Use deterministic seed", key="use_random_seed")
            if st.session_state.use_random_seed:
                st.number_input(
                    "Seed",
                    min_value=0,
                    max_value=2_147_483_646,
                    step=1,
                    key="random_seed_value",
                    help="Same seed + same filters = same artwork order.",
                )

            st.markdown("**Debug Console**")
            if st.button("Clear Logs", key="clear_logs"):
                st.session_state.debug_logs = []
            log_text = "\n".join(st.session_state.debug_logs) if st.session_state.debug_logs else "No logs yet."
            st.code(log_text, language=None)


def render_artwork_display(artwork: dict):
    """Render the current artwork display."""
    idx = st.session_state.current_idx
    total = len(st.session_state.images)

    # Progress
    st.caption(f"Image {idx + 1} of {total}")

    # Layout: image + metadata side-by-side
    col_image, col_meta = st.columns([3, 2], gap="large")

    with col_image:
        image_url = html.escape(str(artwork.get("image_url", "")), quote=True)
        image_title = html.escape(str(artwork.get("title", "Artwork")), quote=True)
        st.markdown(
            f"""
            <div class="art-image-frame">
                <img src="{image_url}" alt="{image_title}">
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_meta:
        title_text = str(artwork.get("title", "Untitled"))
        if artwork.get("source") == "MOMA" and len(title_text) > 150:
            title_text = title_text[:150].rstrip() + "..."
        st.subheader(title_text)

        # Source label
        adapter_names = get_adapter_names()
        source_code = artwork.get("source", "")
        source_name = adapter_names.get(source_code, source_code or "Unknown")
        logo_url = MUSEUM_LOGOS.get(source_code)
        if logo_url:
            logo_class = "museum-logo-moma" if source_code == "MOMA" else ""
            st.markdown(
                (
                    '<div class="museum-source">'
                    f'<img src="{html.escape(logo_url, quote=True)}" '
                    f'class="{logo_class}" '
                    f'alt="{html.escape(source_name, quote=True)} logo" />'
                    f'<span class="museum-source-name">{html.escape(source_name)}</span>'
                    "</div>"
                ),
                unsafe_allow_html=True,
            )
        else:
            st.caption(f"Source: {source_name}")

        # Metadata grid
        meta_left, meta_right = st.columns(2)
        metadata_fields = [
            ("Artist", artwork.get("artist")),
            ("Date", artwork.get("date")),
            ("Type", artwork.get("classification")),
            ("Department", artwork.get("department")),
            ("Medium", artwork.get("medium")),
            ("Credit", artwork.get("credit")),
            ("Culture", artwork.get("culture")),
            ("Place of origin", artwork.get("place_of_origin")),
            (
                "Downloadable",
                "Yes" if artwork.get("is_downloadable", True) else "No",
            ),
            ("Rights", artwork.get("rights_label")),
            ("Accession #", artwork.get("accession_number")),
        ]

        for index, (label, value) in enumerate(metadata_fields):
            if not value:
                continue
            if isinstance(value, list):
                value = ", ".join([str(v) for v in value if v])
            target_col = meta_left if index % 2 == 0 else meta_right
            target_col.write(f"**{label}:** {value}")

        # Actions
        st.markdown("**Actions**")
        col_back, col_skip, col_download = st.columns(3)

        with col_back:
            if st.button("⬅️ Back", type="secondary", disabled=(idx == 0)):
                st.session_state.current_idx -= 1
                st.rerun()

        with col_skip:
            if st.button("⏭️ Skip", type="secondary"):
                st.session_state.current_idx += 1
                st.rerun()

        with col_download:
            if artwork.get("is_downloadable", True):
                download_key_suffix = (
                    f'{artwork.get("source", "SRC")}-{artwork.get("id", "ID")}'
                )
                img_data, mime_type = download_high_res(
                    artwork["image_url"],
                    st.session_state.ssl_bypass,
                )
                if img_data:
                    download_clicked = st.download_button(
                        label="⬇️ Download",
                        data=img_data,
                        file_name=artwork.get("filename", "artwork.jpg"),
                        mime=mime_type or "application/octet-stream",
                        key=f"download_{download_key_suffix}",
                        type="primary",
                    )
                    if download_clicked:
                        log_event(f"Downloaded: {artwork.get('id')}")
                        st.session_state.current_idx += 1
                        st.rerun()
                else:
                    if st.button("Retry", key=f"retry_{download_key_suffix}", type="secondary"):
                        download_high_res.clear()
                        st.rerun()
                    st.button(
                        "⬇️ Download",
                        key=f"download_disabled_{download_key_suffix}",
                        type="primary",
                        disabled=True,
                    )
            else:
                st.button("⬇️ Download", type="primary", disabled=True, key="download_locked")

        # Extended metadata
        metadata = artwork.get("metadata", {})
        if metadata.get("tombstone"):
            st.text_area("Tombstone", value=metadata["tombstone"], height=80, disabled=True)
        if artwork.get("description"):
            st.text_area("Description", value=artwork["description"], height=80, disabled=True)
        if metadata.get("did_you_know"):
            st.text_area("Did you know", value=metadata["did_you_know"], height=60, disabled=True)


def render_source_links(selected_sources: list[str]) -> None:
    """Render selected museum API links."""
    adapter_names = get_adapter_names()
    source_links = {
        "AIC": "https://api.artic.edu/api/v1/artworks/search",
        "CMA": "https://openaccess-api.clevelandart.org/api/artworks",
        "MOMA": "https://github.com/MuseumofModernArt/collection",
    }
    links: list[str] = []
    for source in selected_sources:
        label = adapter_names.get(source, source)
        url = source_links.get(source)
        if url:
            links.append(f"[{label}]({url})")
        else:
            links.append(label)
    if links:
        st.caption("Museums: " + " | ".join(links))


# =============================================================================
# Main Application
# =============================================================================

def main():
    """Main application entry point."""
    # Check for filter changes
    check_filter_changes()

    # Render sidebar
    render_sidebar()

    # Main content
    st.title("Art Findr")
    selected_sources = list(st.session_state.selected_sources)
    adapter_names = get_adapter_names()
    selected_source_names = [adapter_names.get(source, source) for source in selected_sources]
    selected_source_label = ", ".join(selected_source_names)
    render_source_links(selected_sources)

    # Not loaded state
    if not st.session_state.loaded:
        # Show filter feedback from last result if available
        if st.session_state.last_result:
            render_filter_feedback(st.session_state.last_result)
            render_errors(st.session_state.last_result)

        if st.button("Load Artworks", type="primary"):
            log_event("Load button clicked")
            with st.spinner(f"Fetching artworks from {selected_source_label}..."):
                result = fetch_artworks()
                st.session_state.last_result = result

                if result.artworks:
                    # Convert to dicts for session state storage
                    st.session_state.images = [a.to_dict() for a in result.artworks]
                    st.session_state.loaded = True
                    st.rerun()
                else:
                    # Show errors/feedback
                    render_errors(result)
                    render_filter_feedback(result)
                    if not result.errors:
                        st.warning("No artworks found matching your filters. Try adjusting the filters.")

        st.caption("Choose filters in the sidebar, then click Load Artworks.")
        st.caption(
            f"Will fetch up to {st.session_state.fetch_limit} artworks across {len(selected_sources)} museums."
        )
        st.stop()

    # Show filter feedback
    if st.session_state.last_result:
        render_filter_feedback(st.session_state.last_result)

    # No images found
    if not st.session_state.images:
        st.warning("No artworks found. Try adjusting your filters.")
        if st.button("Try Loading Again"):
            log_event("Retry load requested")
            st.session_state.loaded = False
            st.rerun()
        st.stop()

    # All images reviewed
    idx = st.session_state.current_idx
    if idx >= len(st.session_state.images):
        st.success("🎉 You've reviewed all images!")
        if st.button("Start Over"):
            st.session_state.current_idx = 0
            st.rerun()
        st.stop()

    # Display current artwork
    artwork = st.session_state.images[idx]
    render_artwork_display(artwork)


if __name__ == "__main__":
    main()
