import streamlit as st
import requests
from io import BytesIO
from PIL import Image
from datetime import datetime

FETCH_TIMEOUT = 30
IMAGE_TIMEOUT = 30
ORIENTATION_TIMEOUT = 5

st.set_page_config(page_title="Cleveland Museum Portrait Reviewer", layout="wide")

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

def _append_log(level, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"{timestamp} | {level:<5} | {message}"
    st.session_state.debug_logs.append(entry)
    st.session_state.debug_logs = st.session_state.debug_logs[-200:]

def log_event(message):
    _append_log("INFO", message)

def log_error(message):
    _append_log("ERROR", message)

def check_portrait_orientation(img_url):
    """Check if image is portrait orientation by checking image dimensions"""
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
        return height > width  # True if portrait orientation
    except requests.exceptions.RequestException as e:
        log_error(f"Orientation check failed: {e}")
        return False
    except (OSError, ValueError) as e:
        log_error(f"Orientation check failed: {e}")
        return False

def create_readable_filename(title, artist, artwork_id):
    """Create a human-readable filename from title and artist"""
    # Clean up artist name - take first part if there's extra info
    artist_clean = artist.split("(")[0].split(",")[0].strip()
    
    # Combine title and artist, limit length
    filename_base = f"{title} - {artist_clean}"
    
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
    filename = f"{filename_base} ({artwork_id}).jpg"
    
    return filename

def fetch_portraits():
    """Fetch portrait-oriented modern/contemporary art from Cleveland Museum of Art API"""
    try:
        # Search for artworks with images from modern/contemporary periods
        # Using simple parameter-based filtering (not query syntax)
        search_params = {
            "has_image": 1,
            "limit": 1000,  # Much larger limit to find enough matches
            "skip": 0
        }
        
        # Target departments - exact names from Cleveland Museum API
        # Note: "Contemporary Art" and "Photography" don't exist as departments
        target_departments = [
            "Indian and Southeast Asian Art",  # Fixed: "Southeast" is one word
            "Islamic Art",
            "Modern European Painting and Sculpture",
            "American Painting and Sculpture",
            "Prints",
            "Drawings"
        ]
        
        log_event(
            "Fetch start: Cleveland Museum of Art "
            f"(timeout={FETCH_TIMEOUT}s, ssl_bypass={st.session_state.ssl_bypass})"
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
        st.info(f"Filtering {len(artworks)} artworks by department and portrait orientation...")
        progress_bar = st.progress(0)
        
        # Check each artwork for portrait orientation and modern/contemporary date
        for i, artwork_item in enumerate(artworks):
            progress_bar.progress((i + 1) / len(artworks))
            checked += 1
            
            try:
                # Filter by department for modern/contemporary art
                dept = artwork_item.get("department", "")
                dept_str = dept if isinstance(dept, str) else ", ".join(dept) if isinstance(dept, list) else ""
                
                # Check if artwork is from a target department (exact match)
                is_target_dept = dept_str in target_departments
                if not is_target_dept:
                    continue
                
                dept_matches += 1
                
                # Get image URL
                images = artwork_item.get("images", {})
                img_url = images.get("web", {}).get("url") if images else None
                
                if not img_url:
                    continue
                
                # Check if actually portrait orientation
                if not check_portrait_orientation(img_url):
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
                readable_filename = create_readable_filename(title, artist, artwork_id)
                
                # Handle department - can be list or string
                dept = artwork_item.get("department", "")
                if isinstance(dept, list):
                    dept_display = ", ".join(dept)
                else:
                    dept_display = dept if dept else ""
                
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
                    "filename": readable_filename,
                })
                
                # Stop after collecting enough portraits
                if len(portraits) >= 100:
                    break
                    
            except (KeyError, TypeError, ValueError) as e:
                log_error(f"Artwork parse failed for {artwork_item.get('id')}: {e}")
                continue
        
        progress_bar.empty()
        log_event(f"Filter end: {len(portraits)} portraits found")
        st.success(f"Found {len(portraits)} portrait-oriented artworks!")
        st.info(f"Stats: {checked} total checked, {dept_matches} matched departments, {orientation_failures} were landscape")
        return portraits
        
    except requests.exceptions.RequestException as e:
        log_error(f"Fetch failed: {e}")
        st.error(f"Error fetching artworks: {e}")
        return []

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
st.title("🎨 Cleveland Museum Portrait Reviewer")

# Debug sidecar
with st.sidebar:
    st.subheader("Debug Console")
    st.checkbox("Bypass SSL verification (temporary)", key="ssl_bypass")
    if st.session_state.ssl_bypass != st.session_state.ssl_bypass_last:
        status = "ENABLED" if st.session_state.ssl_bypass else "DISABLED"
        log_event(f"SSL verification bypass {status}")
        st.session_state.ssl_bypass_last = st.session_state.ssl_bypass
    if st.button("Clear Logs"):
        st.session_state.debug_logs = []
    log_text = "\n".join(st.session_state.debug_logs) if st.session_state.debug_logs else "No logs yet."
    st.code(log_text)

# Load images button
if not st.session_state.loaded:
    if st.button("Load Portrait Artworks", type="primary"):
        log_event("Load button clicked")
        with st.spinner("Fetching artworks from the Cleveland Museum of Art..."):
            st.session_state.images = fetch_portraits()
            st.session_state.loaded = True
            st.rerun()
    st.info("Click above to load portrait-oriented artworks from Indian/Southeast Asian, Islamic, Modern European, American, Prints, and Drawings departments")
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
st.progress((idx + 1) / len(st.session_state.images))
st.caption(f"Image {idx + 1} of {len(st.session_state.images)}")

# Layout: Image on left, info on right
col1, col2 = st.columns([2, 1])

with col1:
    # Display image at controlled height to prevent scrolling on laptop screens
    st.image(artwork["image_url"], width=600)

with col2:
    st.subheader(artwork["title"])
    st.write(f"**Artist:** {artwork['artist']}")
    st.write(f"**Date:** {artwork['date']}")
    
    if artwork["classification"]:
        st.write(f"**Type:** {artwork['classification']}")
    
    if artwork["department"]:
        st.write(f"**Department:** {artwork['department']}")
    
    if artwork["medium"]:
        with st.expander("Medium Details"):
            st.write(artwork["medium"])
    
    if artwork.get("credit"):
        with st.expander("Credit"):
            st.caption(artwork["credit"])
    
    st.divider()
    
    # Action buttons
    st.write("### Actions")
    
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

# Navigation hint
st.caption("💡 Tip: Use Back/Skip to navigate, or Download to save and move forward")

