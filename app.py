import streamlit as st
import requests
from io import BytesIO
from PIL import Image
from datetime import datetime

FETCH_TIMEOUT = 30
IMAGE_TIMEOUT = 30
ORIENTATION_TIMEOUT = 5
DEFAULT_FETCH_LIMIT = 100
FETCH_LIMIT_OPTIONS = [100, 200, 500, 1000]
ALL_DEPARTMENTS_LABEL = "All departments"

st.set_page_config(page_title="Open Access Art Finder", layout="wide")

# Initialize session state
if "images" not in st.session_state:
    st.session_state.images = []
    st.session_state.current_idx = 0
    st.session_state.loaded = False
if "debug_logs" not in st.session_state:
    st.session_state.debug_logs = []
if "ssl_bypass" not in st.session_state:
    st.session_state.ssl_bypass = False
if "ssl_bypass_last" not in st.session_state:
    st.session_state.ssl_bypass_last = st.session_state.ssl_bypass
if "orientation_filter" not in st.session_state:
    st.session_state.orientation_filter = "Portrait"
if "orientation_filter_last" not in st.session_state:
    st.session_state.orientation_filter_last = st.session_state.orientation_filter
if "department_filter" not in st.session_state:
    st.session_state.department_filter = ALL_DEPARTMENTS_LABEL
if "department_filter_last" not in st.session_state:
    st.session_state.department_filter_last = st.session_state.department_filter
if "fetch_limit" not in st.session_state:
    st.session_state.fetch_limit = DEFAULT_FETCH_LIMIT
if "source" not in st.session_state:
    st.session_state.source = "Cleveland Museum of Art"
if "source_last" not in st.session_state:
    st.session_state.source_last = st.session_state.source
if "aic_search_term" not in st.session_state:
    st.session_state.aic_search_term = "portrait"
if "aic_search_term_last" not in st.session_state:
    st.session_state.aic_search_term_last = st.session_state.aic_search_term
if "aic_departments" not in st.session_state:
    st.session_state.aic_departments = []
if "fetch_limit_last" not in st.session_state:
    st.session_state.fetch_limit_last = st.session_state.fetch_limit

def _append_log(level, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"{timestamp} | {level:<5} | {message}"
    st.session_state.debug_logs.append(entry)
    st.session_state.debug_logs = st.session_state.debug_logs[-200:]

def log_event(message):
    _append_log("INFO", message)

def log_error(message):
    _append_log("ERROR", message)

def reset_loaded_state(reason):
    log_event(f"Reload required: {reason}")
    st.session_state.images = []
    st.session_state.current_idx = 0
    st.session_state.loaded = False

# Handle source changes on any rerun
if st.session_state.source != st.session_state.source_last:
    st.session_state.department_filter = ALL_DEPARTMENTS_LABEL
    st.session_state.aic_departments = []
    reset_loaded_state("source changed")
    st.session_state.source_last = st.session_state.source

KNOWN_DEPARTMENTS = [
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

def normalize_department(raw_department):
    if isinstance(raw_department, list):
        return ", ".join([dept for dept in raw_department if dept])
    if isinstance(raw_department, str):
        return raw_department.strip()
    return ""

def department_matches(selected_department, item_department):
    if selected_department == ALL_DEPARTMENTS_LABEL:
        return True
    return item_department == selected_department

def get_department_options():
    if st.session_state.source == "Art Institute of Chicago":
        if st.session_state.aic_departments:
            return [ALL_DEPARTMENTS_LABEL] + st.session_state.aic_departments
        return [ALL_DEPARTMENTS_LABEL]
    return [ALL_DEPARTMENTS_LABEL] + KNOWN_DEPARTMENTS

def _orientation_match(width, height, orientation):
    is_portrait = height > width
    if orientation == "Portrait":
        return is_portrait
    if orientation == "Landscape":
        return not is_portrait
    return False

def check_portrait_orientation(img_url, orientation):
    """Check if image orientation matches by checking image dimensions"""
    try:
        response = requests.get(
            img_url,
            stream=True,
            timeout=ORIENTATION_TIMEOUT,
            verify=not st.session_state.ssl_bypass
        )
        response.raise_for_status()
        img = Image.open(BytesIO(response.content))
        width, height = img.size
        return _orientation_match(width, height, orientation)
    except requests.exceptions.RequestException as e:
        log_error(f"Orientation check failed: {e}")
        return False
    except (OSError, ValueError) as e:
        log_error(f"Orientation check failed: {e}")
        return False

def create_readable_filename(title, artwork_id, museum_abbrev="CMA"):
    """Create a human-readable filename from museum abbreviation and title"""
    filename_base = f"{museum_abbrev}-{title}"
    
    # Remove or replace invalid filename characters
    invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for char in invalid_chars:
        filename_base = filename_base.replace(char, '')
    
    # Replace multiple spaces with single space
    filename_base = ' '.join(filename_base.split())
    
    # Limit total length (leaving room for .jpg)
    max_length = 100
    if len(filename_base) > max_length:
        filename_base = filename_base[:max_length].strip()
    
    # Add artwork ID at end to ensure uniqueness
    filename = f"{filename_base}-{artwork_id}.jpg"
    
    return filename

def fetch_cma_artworks():
    """Fetch artworks from Cleveland Museum of Art API"""
    try:
        # Search for artworks with images from modern/contemporary periods
        # Using simple parameter-based filtering (not query syntax)
        search_params = {
            "has_image": 1,
            "limit": st.session_state.fetch_limit,
            "skip": 0
        }
        
        log_event(
            "Fetch start: Cleveland Museum of Art "
            f"(timeout={FETCH_TIMEOUT}s, ssl_bypass={st.session_state.ssl_bypass}, "
            f"orientation={st.session_state.orientation_filter}, "
            f"department={st.session_state.department_filter}, "
            f"limit={st.session_state.fetch_limit})"
        )
        st.info("Fetching artworks from Cleveland Museum of Art...")
        
        response = requests.get(
            "https://openaccess-api.clevelandart.org/api/artworks",
            params=search_params,
            timeout=FETCH_TIMEOUT,
            verify=not st.session_state.ssl_bypass
        )
        response.raise_for_status()
        log_event(f"Fetch success: status {response.status_code}")
        data = response.json()
        
        artworks = data.get("data", [])
        
        portraits = []
        checked = 0
        dept_matches = 0
        orientation_failures = 0
        
        log_event(f"Filter start: {len(artworks)} artworks")
        st.info(
            f"Filtering {len(artworks)} artworks by department and "
            f"{st.session_state.orientation_filter.lower()} orientation..."
        )
        progress_bar = st.progress(0)
        
        # Check each artwork for portrait orientation and modern/contemporary date
        for i, artwork_item in enumerate(artworks):
            progress_bar.progress((i + 1) / len(artworks))
            checked += 1
            
            try:
                # Filter by department for modern/contemporary art
                dept_str = normalize_department(artwork_item.get("department", ""))
                
                # Check if artwork matches selected department (exact match)
                if not department_matches(st.session_state.department_filter, dept_str):
                    continue
                
                if dept_str:
                    dept_matches += 1
                else:
                    continue
                
                # Get image URL
                images = artwork_item.get("images", {})
                img_url = images.get("web", {}).get("url") if images else None
                
                if not img_url:
                    continue
                
                # Check if actually portrait orientation
                if not check_portrait_orientation(img_url, st.session_state.orientation_filter):
                    orientation_failures += 1
                    continue
                
                # Extract artist info
                creators = artwork_item.get("creators", [])
                if creators:
                    artist = creators[0].get("description", "Unknown")
                elif artwork_item.get("culture"):
                    artist = artwork_item.get("culture", ["Unknown"])[0] if isinstance(artwork_item.get("culture"), list) else artwork_item.get("culture", "Unknown")
                else:
                    artist = "Unknown"
                
                # Create human-readable filename
                title = artwork_item.get("title", "Untitled")
                artwork_id = artwork_item.get("id")
                readable_filename = create_readable_filename(title, artwork_id, museum_abbrev="CMA")
                
                dept_display = dept_str
                
                portraits.append({
                    "id": artwork_id,
                    "image_url": img_url,
                    "title": title,
                    "artist": artist,
                    "date": artwork_item.get("creation_date", ""),
                    "medium": artwork_item.get("technique", ""),
                    "department": dept_display,
                    "classification": artwork_item.get("type", ""),
                    "credit": artwork_item.get("creditline", ""),
                    "culture": artwork_item.get("culture", ""),
                    "dimensions": artwork_item.get("dimensions", ""),
                    "tombstone": artwork_item.get("tombstone", ""),
                    "description": artwork_item.get("description", ""),
                    "did_you_know": artwork_item.get("did_you_know", ""),
                    "share_license_status": artwork_item.get("share_license_status", ""),
                    "accession_number": artwork_item.get("accession_number", ""),
                    "filename": readable_filename,
                })
                
                # Stop after collecting enough artworks
                if len(portraits) >= st.session_state.fetch_limit:
                    break
                    
            except (KeyError, TypeError, ValueError) as e:
                log_error(f"Artwork parse failed for {artwork_item.get('id')}: {e}")
                continue
        
        progress_bar.empty()
        log_event(f"Filter end: {len(portraits)} portraits found")
        st.success(f"Found {len(portraits)} artworks!")
        st.info(f"Stats: {checked} total checked, {dept_matches} matched departments, {orientation_failures} were landscape")
        return portraits
        
    except requests.exceptions.RequestException as e:
        log_error(f"Fetch failed: {e}")
        st.error(f"Error fetching artworks: {e}")
        return []

def fetch_aic_artworks():
    """Fetch artworks from Art Institute of Chicago API (search endpoint)"""
    try:
        fields = ",".join([
            "id",
            "title",
            "artist_display",
            "date_display",
            "medium_display",
            "department_title",
            "classification_title",
            "credit_line",
            "image_id",
            "thumbnail",
            "place_of_origin",
            "accession_number",
            "api_link",
        ])
        params = {
            "q": st.session_state.aic_search_term,
            "limit": st.session_state.fetch_limit,
            "fields": fields,
        }
        log_event(
            "Fetch start: Art Institute of Chicago "
            f"(timeout={FETCH_TIMEOUT}s, ssl_bypass={st.session_state.ssl_bypass}, "
            f"q={st.session_state.aic_search_term}, limit={st.session_state.fetch_limit})"
        )
        response = requests.get(
            "https://api.artic.edu/api/v1/artworks/search",
            params=params,
            timeout=FETCH_TIMEOUT,
            verify=not st.session_state.ssl_bypass
        )
        response.raise_for_status()
        data = response.json()
        iiif_url = data.get("config", {}).get("iiif_url", "https://www.artic.edu/iiif/2")
        artworks = data.get("data", [])
        log_event(f"Fetch success: status {response.status_code}")

        portraits = []
        checked = 0
        dept_matches = 0
        orientation_failures = 0
        departments = set()

        log_event(f"Filter start: {len(artworks)} artworks")
        st.info(
            f"Filtering {len(artworks)} artworks by department and "
            f"{st.session_state.orientation_filter.lower()} orientation..."
        )
        progress_bar = st.progress(0)

        for i, artwork_item in enumerate(artworks):
            progress_bar.progress((i + 1) / max(len(artworks), 1))
            checked += 1

            try:
                dept = normalize_department(artwork_item.get("department_title", ""))
                if dept:
                    departments.add(dept)

                if not department_matches(st.session_state.department_filter, dept):
                    continue
                if dept:
                    dept_matches += 1

                image_id = artwork_item.get("image_id")
                if not image_id:
                    continue
                img_url = f"{iiif_url}/{image_id}/full/843,/0/default.jpg"

                thumb = artwork_item.get("thumbnail") or {}
                width = thumb.get("width")
                height = thumb.get("height")
                if width and height:
                    if not _orientation_match(width, height, st.session_state.orientation_filter):
                        orientation_failures += 1
                        continue
                else:
                    if not check_portrait_orientation(img_url, st.session_state.orientation_filter):
                        orientation_failures += 1
                        continue

                title = artwork_item.get("title", "Untitled")
                artwork_id = artwork_item.get("id")
                readable_filename = create_readable_filename(title, artwork_id, museum_abbrev="AIC")

                portraits.append({
                    "id": artwork_id,
                    "image_url": img_url,
                    "title": title,
                    "artist": artwork_item.get("artist_display", "Unknown"),
                    "date": artwork_item.get("date_display", ""),
                    "medium": artwork_item.get("medium_display", ""),
                    "department": dept,
                    "classification": artwork_item.get("classification_title", ""),
                    "credit": artwork_item.get("credit_line", ""),
                    "culture": artwork_item.get("place_of_origin", ""),
                    "description": (thumb.get("alt_text") or ""),
                    "did_you_know": "",
                    "share_license_status": "",
                    "accession_number": artwork_item.get("accession_number", ""),
                    "filename": readable_filename,
                })

                if len(portraits) >= st.session_state.fetch_limit:
                    break

            except (KeyError, TypeError, ValueError) as e:
                log_error(f"AIC parse failed for {artwork_item.get('id')}: {e}")
                continue

        progress_bar.empty()
        st.session_state.aic_departments = sorted(departments)
        log_event(f"Filter end: {len(portraits)} artworks found")
        st.success(f"Found {len(portraits)} artworks!")
        st.info(f"Stats: {checked} total checked, {dept_matches} matched departments, {orientation_failures} were landscape")
        return portraits

    except requests.exceptions.RequestException as e:
        log_error(f"Fetch failed: {e}")
        st.error(f"Error fetching artworks: {e}")
        return []

def fetch_artworks():
    if st.session_state.source == "Art Institute of Chicago":
        return fetch_aic_artworks()
    return fetch_cma_artworks()

def download_high_res(image_url):
    """Download high-resolution image"""
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
        raise

# Main UI
st.markdown("### Open Access Art Finder")
if st.session_state.source == "Art Institute of Chicago":
    st.caption("[Art Institute of Chicago API](https://api.artic.edu/api/v1/artworks/search)")
else:
    st.caption("[Cleveland Museum of Art Open Access API](https://openaccess-api.clevelandart.org/api/artworks)")

# Debug sidecar
with st.sidebar:
    st.subheader("Filters")
    st.selectbox(
        "Source",
        ["Cleveland Museum of Art", "Art Institute of Chicago"],
        key="source"
    )
    st.text_input(
        "Search term (AIC only)",
        value=st.session_state.aic_search_term,
        key="aic_search_term",
        help="Used for AIC only; ignored for Cleveland."
    )
    st.selectbox(
        "Orientation",
        ["Portrait", "Landscape"],
        key="orientation_filter"
    )
    dept_options = get_department_options()
    if st.session_state.department_filter not in dept_options:
        st.session_state.department_filter = ALL_DEPARTMENTS_LABEL
    st.selectbox(
        "Department",
        dept_options,
        key="department_filter"
    )
    if (
        st.session_state.source == "Art Institute of Chicago"
        and not st.session_state.aic_departments
    ):
        st.caption("AIC departments appear after the first load.")
    st.selectbox(
        "Fetch limit",
        FETCH_LIMIT_OPTIONS,
        key="fetch_limit"
    )
    st.caption("Filters apply on load.")
    st.checkbox("Bypass SSL verification (temporary)", key="ssl_bypass")
    # Reset loaded state when filters change so the user can reload cleanly
    if (
        st.session_state.source == "Art Institute of Chicago"
        and st.session_state.aic_search_term != st.session_state.aic_search_term_last
    ):
        reset_loaded_state("AIC search term changed")
        st.session_state.aic_search_term_last = st.session_state.aic_search_term
    if st.session_state.orientation_filter != st.session_state.orientation_filter_last:
        reset_loaded_state("orientation changed")
        st.session_state.orientation_filter_last = st.session_state.orientation_filter
    if st.session_state.department_filter != st.session_state.department_filter_last:
        reset_loaded_state("department changed")
        st.session_state.department_filter_last = st.session_state.department_filter
    if st.session_state.fetch_limit != st.session_state.fetch_limit_last:
        reset_loaded_state("fetch limit changed")
        st.session_state.fetch_limit_last = st.session_state.fetch_limit
    if st.session_state.ssl_bypass != st.session_state.ssl_bypass_last:
        status = "ENABLED" if st.session_state.ssl_bypass else "DISABLED"
        log_event(f"SSL verification bypass {status}")
        st.session_state.ssl_bypass_last = st.session_state.ssl_bypass
    with st.expander("Debug Console", expanded=False):
        if st.button("Clear Logs"):
            st.session_state.debug_logs = []
        log_text = "\n".join(st.session_state.debug_logs) if st.session_state.debug_logs else "No logs yet."
        st.code(log_text)

# Load images button
if not st.session_state.loaded:
    if st.button("Load Artworks", type="primary"):
        log_event("Load button clicked")
        with st.spinner("Fetching artworks..."):
            st.session_state.images = fetch_artworks()
            st.session_state.loaded = True
            st.rerun()
    st.caption("Choose filters, then click Load Artworks.")
    if st.session_state.source == "Art Institute of Chicago":
        st.caption(f"Load up to {st.session_state.fetch_limit} artworks from the AIC API search endpoint")
    else:
        st.caption(f"Load up to {st.session_state.fetch_limit} artworks from the Cleveland Museum of Art API")
    st.stop()

# Check if we have images
if not st.session_state.images:
    st.warning("No portrait images found. Try loading again.")
    if st.button("Try Loading Again"):
        log_event("Retry load requested")
        st.session_state.loaded = False
        st.rerun()
    st.stop()

# Current image
idx = st.session_state.current_idx
if idx >= len(st.session_state.images):
    st.success("🎉 You've reviewed all images!")
    if st.button("Start Over"):
        st.session_state.current_idx = 0
        st.rerun()
    st.stop()

artwork = st.session_state.images[idx]

# Progress
st.caption(f"Image {idx + 1} of {len(st.session_state.images)}")

# Layout: compact image + metadata side-by-side
col_image, col_meta = st.columns([3, 2], gap="large")

with col_image:
    st.image(artwork["image_url"], use_container_width=True)

with col_meta:
    st.subheader(artwork["title"])
    source_label = "Cleveland Museum of Art"
    if st.session_state.source == "Art Institute of Chicago":
        source_label = "Art Institute of Chicago"
    st.caption(f"Source: {source_label}")

    meta_left, meta_right = st.columns(2)
    metadata_fields = [
        ("Artist", artwork["artist"]),
        ("Date", artwork["date"]),
        ("Type", artwork["classification"]),
        ("Department", artwork["department"]),
        ("Medium", artwork["medium"]),
        ("Credit", artwork.get("credit")),
        ("Culture", artwork.get("culture")),
        ("Accession #", artwork.get("accession_number")),
        ("Share license", artwork.get("share_license_status")),
    ]

    for index, (label, value) in enumerate(metadata_fields):
        if not value:
            continue
        if isinstance(value, list):
            value = ", ".join([str(v) for v in value if v])
        target_col = meta_left if index % 2 == 0 else meta_right
        target_col.write(f"**{label}:** {value}")

    st.markdown("**Actions**")
    col_back, col_skip, col_download = st.columns(3)

    with col_back:
        # Back button - disabled if on first image
        if st.button("⬅️ Back", type="secondary", width='stretch', disabled=(st.session_state.current_idx == 0)):
            st.session_state.current_idx -= 1
            st.rerun()

    with col_skip:
        if st.button("⏭️ Skip", type="secondary", width='stretch'):
            st.session_state.current_idx += 1
            st.rerun()

    with col_download:
        # Single-click download
        img_data = None
        try:
            img_data = download_high_res(artwork["image_url"])
        except requests.exceptions.RequestException as e:
            log_error(f"Download prep failed for {artwork.get('id')}: {e}")
            st.error("Download failed. Please try again.")
        if img_data is None:
            st.button("⬇️ Download", type="primary", width='stretch', disabled=True)
        else:
            download_clicked = st.download_button(
                label="⬇️ Download",
                data=img_data,
                file_name=artwork["filename"],
                mime="image/jpeg",
                type="primary",
                width='stretch'
            )
            if download_clicked:
                log_event(f"Download clicked: {artwork.get('id')}")
                st.session_state.current_idx += 1
                st.rerun()

    if artwork.get("tombstone"):
        st.text_area("Tombstone", value=artwork.get("tombstone"), height=80, disabled=True)
    if artwork.get("description"):
        st.text_area("Description", value=artwork.get("description"), height=80, disabled=True)
    if artwork.get("did_you_know"):
        st.text_area("Did you know", value=artwork.get("did_you_know"), height=60, disabled=True)

# Navigation hint removed to keep content above the fold

