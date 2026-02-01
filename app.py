"""Open Access Art Finder - Streamlit application."""

import streamlit as st
import requests
from datetime import datetime

from art_finder.adapters import get_adapter, get_adapter_names
from art_finder.models import SearchFilters, AdapterResult
from art_finder.mappings import get_canonical_departments

# Configuration
FETCH_TIMEOUT = 30
IMAGE_TIMEOUT = 30
DEFAULT_FETCH_LIMIT = 100
FETCH_LIMIT_OPTIONS = [100, 200, 500, 1000]
ALL_DEPARTMENTS_LABEL = "All departments"

st.set_page_config(page_title="Open Access Art Finder", layout="wide")


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
        "source": "CMA",
        "source_last": "CMA",
        "orientation_filter": "Portrait",
        "orientation_filter_last": "Portrait",
        "department_filter": ALL_DEPARTMENTS_LABEL,
        "department_filter_last": ALL_DEPARTMENTS_LABEL,
        "fetch_limit": DEFAULT_FETCH_LIMIT,
        "fetch_limit_last": DEFAULT_FETCH_LIMIT,
        # New filters
        "year_from": None,
        "year_from_last": None,
        "year_to": None,
        "year_to_last": None,
        "min_width": None,
        "min_width_last": None,
        "min_height": None,
        "min_height_last": None,
        # AIC-specific
        "aic_search_term": "portrait",
        "aic_search_term_last": "portrait",
        "aic_departments": [],
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
    
    # Check each filter
    filter_checks = [
        ("source", "source changed"),
        ("orientation_filter", "orientation changed"),
        ("department_filter", "department changed"),
        ("fetch_limit", "fetch limit changed"),
        ("year_from", "year range changed"),
        ("year_to", "year range changed"),
        ("min_width", "resolution changed"),
        ("min_height", "resolution changed"),
        ("aic_search_term", "search term changed"),
        ("ssl_bypass", "SSL bypass changed"),
    ]
    
    for key, reason in filter_checks:
        last_key = f"{key}_last"
        if st.session_state.get(key) != st.session_state.get(last_key):
            changes.append(reason)
            st.session_state[last_key] = st.session_state[key]
    
    # Special handling for source change - reset department
    if "source changed" in changes:
        st.session_state.department_filter = ALL_DEPARTMENTS_LABEL
        st.session_state.aic_departments = []
    
    # Reset if any changes
    if changes:
        # Deduplicate reasons
        unique_reasons = list(dict.fromkeys(changes))
        reset_loaded_state(", ".join(unique_reasons))


# =============================================================================
# Artwork Fetching
# =============================================================================

def fetch_artworks() -> AdapterResult:
    """Fetch artworks using the selected adapter."""
    source = st.session_state.source
    adapter = get_adapter(source)
    adapter.set_logger(adapter_log_callback)
    
    # Build filters
    filters = SearchFilters(
        query=st.session_state.aic_search_term if source == "AIC" else None,
        year_from=st.session_state.year_from,
        year_to=st.session_state.year_to,
        department=(
            None if st.session_state.department_filter == ALL_DEPARTMENTS_LABEL 
            else st.session_state.department_filter
        ),
        orientation=st.session_state.orientation_filter,
        min_width=st.session_state.min_width,
        min_height=st.session_state.min_height,
        has_image=True,
        limit=st.session_state.fetch_limit,
        ssl_bypass=st.session_state.ssl_bypass,
    )
    
    log_event(f"Fetching from {adapter.name}...")
    
    # Execute search
    result = adapter.search(filters)
    
    # Update discovered departments for AIC
    if source == "AIC":
        st.session_state.aic_departments = adapter.get_departments()
    
    return result


def download_high_res(image_url: str) -> bytes | None:
    """Download high-resolution image."""
    try:
        response = requests.get(
            image_url,
            timeout=IMAGE_TIMEOUT,
            verify=not st.session_state.ssl_bypass
        )
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        log_error(f"Download failed: {e}")
        return None


# =============================================================================
# UI Components
# =============================================================================

def render_filter_feedback(result: AdapterResult):
    """Render feedback about which filters were applied/skipped."""
    if not result:
        return
    
    status = result.filter_status
    
    # Show applied filters
    if status.applied:
        with st.expander("✓ Filters Applied", expanded=False):
            for name, desc in status.applied.items():
                st.caption(f"• {desc}")
    
    # Show skipped filters (warnings)
    if status.skipped:
        with st.expander("⚠️ Filters Skipped", expanded=True):
            for name, reason in status.skipped.items():
                st.warning(reason)
    
    # Show warnings
    if result.warnings:
        for warning in result.warnings:
            st.warning(warning)


def render_errors(result: AdapterResult):
    """Render any errors from the adapter."""
    if not result or not result.errors:
        return
    
    for error in result.errors:
        st.error(error)


def get_department_options() -> list[str]:
    """Get department options based on current source."""
    # Use canonical departments for unified UI
    canonical = get_canonical_departments()
    
    # Also include source-specific departments for backward compatibility
    if st.session_state.source == "AIC":
        # Add any discovered AIC departments not in canonical
        aic_depts = st.session_state.aic_departments
        if aic_depts:
            all_depts = set(canonical) | set(aic_depts)
            return [ALL_DEPARTMENTS_LABEL] + sorted(all_depts)
        return [ALL_DEPARTMENTS_LABEL] + canonical
    else:
        # CMA - use canonical plus CMA-specific
        adapter = get_adapter("CMA")
        cma_depts = adapter.get_departments()
        all_depts = set(canonical) | set(cma_depts)
        return [ALL_DEPARTMENTS_LABEL] + sorted(all_depts)


def render_sidebar():
    """Render the sidebar with filters and debug console."""
    with st.sidebar:
        st.subheader("Filters")
        
        # Source selector
        adapter_names = get_adapter_names()
        source_options = list(adapter_names.keys())
        source_labels = [adapter_names[k] for k in source_options]
        
        current_idx = source_options.index(st.session_state.source) if st.session_state.source in source_options else 0
        selected_label = st.selectbox(
            "Source",
            source_labels,
            index=current_idx,
        )
        st.session_state.source = source_options[source_labels.index(selected_label)]
        
        # Search term (AIC only)
        if st.session_state.source == "AIC":
            st.text_input(
                "Search term",
                value=st.session_state.aic_search_term,
                key="aic_search_term",
                help="Search term for Art Institute of Chicago"
            )
        
        # Orientation
        st.selectbox(
            "Orientation",
            ["Portrait", "Landscape"],
            key="orientation_filter"
        )
        
        # Department
        dept_options = get_department_options()
        if st.session_state.department_filter not in dept_options:
            st.session_state.department_filter = ALL_DEPARTMENTS_LABEL
        
        st.selectbox(
            "Department",
            dept_options,
            key="department_filter",
            help="Filter by curatorial department"
        )
        
        # Year range
        st.markdown("**Year Range**")
        col1, col2 = st.columns(2)
        with col1:
            year_from = st.number_input(
                "From",
                min_value=-3000,
                max_value=2030,
                value=st.session_state.year_from,
                placeholder="Any",
                help="Earliest year (e.g., 1850)",
            )
            st.session_state.year_from = year_from if year_from else None
        with col2:
            year_to = st.number_input(
                "To",
                min_value=-3000,
                max_value=2030,
                value=st.session_state.year_to,
                placeholder="Any",
                help="Latest year (e.g., 1950)",
            )
            st.session_state.year_to = year_to if year_to else None
        
        # Resolution filter
        st.markdown("**Minimum Resolution**")
        col1, col2 = st.columns(2)
        with col1:
            min_w = st.number_input(
                "Width",
                min_value=0,
                max_value=10000,
                value=st.session_state.min_width or 0,
                help="Minimum width in pixels",
            )
            st.session_state.min_width = min_w if min_w > 0 else None
        with col2:
            min_h = st.number_input(
                "Height",
                min_value=0,
                max_value=10000,
                value=st.session_state.min_height or 0,
                help="Minimum height in pixels",
            )
            st.session_state.min_height = min_h if min_h > 0 else None
        
        # Fetch limit
        st.selectbox(
            "Fetch limit",
            FETCH_LIMIT_OPTIONS,
            key="fetch_limit"
        )
        
        st.caption("Filters apply when you click Load Artworks.")
        
        # SSL bypass option
        st.checkbox("Bypass SSL verification", key="ssl_bypass", help="Use if you encounter SSL errors")
        
        # Debug console
        with st.expander("Debug Console", expanded=False):
            if st.button("Clear Logs"):
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
        st.image(artwork["image_url"], use_container_width=True)
    
    with col_meta:
        st.subheader(artwork["title"])
        
        # Source label
        adapter_names = get_adapter_names()
        source_name = adapter_names.get(artwork.get("source", ""), artwork.get("source", "Unknown"))
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
            img_data = download_high_res(artwork["image_url"])
            if img_data:
                download_clicked = st.download_button(
                    label="⬇️ Download",
                    data=img_data,
                    file_name=artwork.get("filename", "artwork.jpg"),
                    mime="image/jpeg",
                    type="primary",
                )
                if download_clicked:
                    log_event(f"Downloaded: {artwork.get('id')}")
                    st.session_state.current_idx += 1
                    st.rerun()
            else:
                st.button("⬇️ Download", type="primary", disabled=True)
        
        # Extended metadata
        metadata = artwork.get("metadata", {})
        if metadata.get("tombstone"):
            st.text_area("Tombstone", value=metadata["tombstone"], height=80, disabled=True)
        if artwork.get("description"):
            st.text_area("Description", value=artwork["description"], height=80, disabled=True)
        if metadata.get("did_you_know"):
            st.text_area("Did you know", value=metadata["did_you_know"], height=60, disabled=True)


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
    st.markdown("### Open Access Art Finder")
    
    # Show source link
    adapter_names = get_adapter_names()
    source_name = adapter_names.get(st.session_state.source, st.session_state.source)
    if st.session_state.source == "AIC":
        st.caption(f"[{source_name} API](https://api.artic.edu/api/v1/artworks/search)")
    else:
        st.caption(f"[{source_name} Open Access API](https://openaccess-api.clevelandart.org/api/artworks)")
    
    # Not loaded state
    if not st.session_state.loaded:
        # Show filter feedback from last result if available
        if st.session_state.last_result:
            render_filter_feedback(st.session_state.last_result)
            render_errors(st.session_state.last_result)
        
        if st.button("Load Artworks", type="primary"):
            log_event("Load button clicked")
            with st.spinner(f"Fetching artworks from {source_name}..."):
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
        st.caption(f"Will fetch up to {st.session_state.fetch_limit} artworks from {source_name}")
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
