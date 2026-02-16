"""Help page — field mapping visualization and reference."""

from __future__ import annotations

import streamlit as st

from art_finder.mappings.departments import (
    CANONICAL_GENRES,
    CANONICAL_MEDIA,
    DEPARTMENT_MAP,
)
from art_finder.mappings.field_enums import (
    MEDIUM_KEYWORD_MAP,
    MUSEUM_FIELD_MAP,
)
from art_finder.mappings.sankey_builder import build_genre_sankey, build_medium_sankey

st.set_page_config(page_title="Art Findr – Help", layout="wide")

import streamlit.components.v1 as components

st.markdown(
    """
<style>
.block-container {
    padding-top: 0.9rem;
}
</style>
""",
    unsafe_allow_html=True,
)

with st.sidebar:
    with st.expander("Pages", expanded=False):
        st.page_link("app.py", label="App")
        st.page_link("pages/help.py", label="Help")


def _render_plotly_html(fig) -> None:
    """Render a Plotly figure as raw HTML with clip-paths removed.

    Plotly Sankey applies SVG <clipPath> that hides node labels near the
    edges.  By rendering via components.html we can inject a post-render
    script that strips those clip-paths.
    """
    raw_html = fig.to_html(include_plotlyjs="cdn", full_html=False)
    html = f"""
    <div id="plotly-wrapper">{raw_html}</div>
    <script>
    // Wait for Plotly to render, then remove clip-paths
    requestAnimationFrame(function check() {{
        var els = document.querySelectorAll('.sankey [clip-path]');
        if (els.length) {{
            els.forEach(function(el) {{ el.removeAttribute('clip-path'); }});
            document.querySelectorAll('svg').forEach(function(s) {{
                s.style.overflow = 'visible';
            }});
        }} else {{
            requestAnimationFrame(check);
        }}
    }});
    </script>
    """
    components.html(html, height=fig.layout.height + 20, scrolling=False)

st.title("Help")

# ------------------------------------------------------------------
# Section: Field Mappings
# ------------------------------------------------------------------
st.header("Field Mappings")
st.markdown(
    "The diagrams below show how **Art Findr filter values** map to "
    "**museum-specific fields** across the Cleveland Museum of Art, "
    "Art Institute of Chicago, and Museum of Modern Art.  \n"
    "Hover over nodes for field names and match details. "
    "Use the detail panels below each chart to inspect individual mappings."
)

tab_genre, tab_medium, tab_other = st.tabs(
    ["Genre / Department", "Medium", "Other Fields"]
)

# ── helpers ────────────────────────────────────────────────────────

_MUSEUMS = [
    ("cma", "Cleveland Museum of Art", "CMA"),
    ("aic", "Art Institute of Chicago", "AIC"),
    ("moma", "Museum of Modern Art", "MoMA"),
]


def _ensure_list(val: str | list[str] | None) -> list[str]:
    if val is None:
        return []
    if isinstance(val, str):
        return [val]
    return list(val)


def _render_genre_detail() -> None:
    """Detail panel: pick a canonical genre and see per-museum breakdown."""
    selected = st.selectbox("Inspect a genre", CANONICAL_GENRES, key="genre_detail")
    if not selected:
        return
    mapping = DEPARTMENT_MAP.get(selected, {})

    cols = st.columns(len(_MUSEUMS))
    for col, (key, full_name, short_key) in zip(cols, _MUSEUMS):
        with col:
            with st.expander(full_name, expanded=True):
                field_meta = MUSEUM_FIELD_MAP.get(short_key, {}).get("genre", {})
                src = ", ".join(field_meta.get("source_fields", []))
                st.markdown(f"**Source field(s):** `{src}`")
                st.markdown(f"**Match strategy:** {field_meta.get('match', '—')}")

                vals = _ensure_list(mapping.get(key))
                if vals:
                    st.markdown("**Mapped values:**")
                    for v in vals:
                        st.markdown(f"- `{v}`")
                else:
                    st.info("No mapping for this museum.")

                enum_list = field_meta.get("enum")
                if enum_list:
                    with st.expander(
                        f"All {full_name} departments ({len(enum_list)})"
                    ):
                        st.code("\n".join(enum_list))


def _render_medium_detail() -> None:
    """Detail panel: pick a canonical medium and see per-museum breakdown."""
    selected = st.selectbox("Inspect a medium", CANONICAL_MEDIA, key="medium_detail")
    if not selected:
        return

    cols = st.columns(len(_MUSEUMS))
    for col, (key, full_name, short_key) in zip(cols, _MUSEUMS):
        with col:
            with st.expander(full_name, expanded=True):
                field_meta = MUSEUM_FIELD_MAP.get(short_key, {}).get("medium", {})
                src = ", ".join(field_meta.get("source_fields", []))
                st.markdown(f"**Source field(s):** `{src}`")
                st.markdown(f"**Match strategy:** {field_meta.get('match', '—')}")

                keywords = MEDIUM_KEYWORD_MAP.get(selected, {}).get(key, [])
                if keywords:
                    st.markdown("**Keywords:**")
                    for kw in keywords:
                        st.markdown(f"- `{kw}`")
                else:
                    st.info("No keywords for this museum.")

                enum_list = field_meta.get("enum")
                samples = field_meta.get("samples")
                if enum_list:
                    with st.expander(
                        f"All {full_name} values ({len(enum_list)})"
                    ):
                        st.code("\n".join(enum_list))
                elif samples:
                    with st.expander(
                        f"Sample {full_name} values ({len(samples)})"
                    ):
                        st.code("\n".join(samples))


# ── Tab: Genre / Department ───────────────────────────────────────

_COLUMN_HEADERS_GENRE = [
    ("Art Findr", "canonical genre"),
    ("Cleveland Museum of Art", "department"),
    ("Art Institute of Chicago", "department_title"),
    ("Museum of Modern Art", "keyword contains"),
]

_COLUMN_HEADERS_MEDIUM = [
    ("Art Findr", "canonical medium"),
    ("Cleveland Museum of Art", "technique / type"),
    ("Art Institute of Chicago", "medium_display"),
    ("Museum of Modern Art", "Medium / Classification"),
]


def _render_column_headers(headers: list[tuple[str, str]]) -> None:
    cols = st.columns(len(headers))
    for col, (name, field) in zip(cols, headers):
        with col:
            st.markdown(f"**{name}**  \n*field: {field}*")


with tab_genre:
    _render_column_headers(_COLUMN_HEADERS_GENRE)
    fig_genre = build_genre_sankey()
    _render_plotly_html(fig_genre)
    st.subheader("Genre Detail")
    _render_genre_detail()

# ── Tab: Medium ───────────────────────────────────────────────────

with tab_medium:
    _render_column_headers(_COLUMN_HEADERS_MEDIUM)
    fig_medium = build_medium_sankey()
    _render_plotly_html(fig_medium)
    st.subheader("Medium Detail")
    _render_medium_detail()

# ── Tab: Other Fields ─────────────────────────────────────────────

with tab_other:
    st.info("Additional field mappings will be documented here as they are added.")
