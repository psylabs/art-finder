"""Build Plotly Sankey diagrams for field mapping visualization.

Creates multi-column Sankey diagrams where:
- Column 0: Art Findr canonical values (genre or medium)
- Columns 1..N: One column per museum, showing that museum's mapped values

Links chain through columns so the flow reads left to right:
  Canonical → Museum 1 values → Museum 2 values → Museum 3 values
"""

from __future__ import annotations

import plotly.graph_objects as go

from .departments import DEPARTMENT_MAP, CANONICAL_GENRES, CANONICAL_MEDIA
from .field_enums import MEDIUM_KEYWORD_MAP, MUSEUM_FIELD_MAP

# (dept_map_key, display_name, field_name_for_genre, color)
_MUSEUMS = [
    ("cma", "Cleveland Museum of Art", "department", "#1f77b4"),
    ("aic", "Art Institute of Chicago", "department_title", "#ff7f0e"),
    ("moma", "Museum of Modern Art", "keywords", "#2ca02c"),
]

_CANONICAL_COLOR = "#7f7f7f"


def _ensure_list(val: str | list[str] | None) -> list[str]:
    if val is None:
        return []
    if isinstance(val, str):
        return [val]
    return list(val)


def _hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def build_genre_sankey() -> go.Figure:
    """Multi-column Sankey: Art Findr genre → per-museum department values."""

    num_cols = 1 + len(_MUSEUMS)  # canonical + each museum
    col_x = [i / (num_cols - 1) for i in range(num_cols)]
    # Inset edge columns so node text labels don't clip outside the chart.
    col_x[0] = 0.001
    col_x[-1] = 0.999

    labels: list[str] = []
    colors: list[str] = []
    hover: list[str] = []
    node_x: list[float] = []
    node_y: list[float] = []
    sources: list[int] = []
    targets: list[int] = []
    link_colors: list[str] = []

    # -- Column 0: canonical genres --
    canon_indices: dict[str, int] = {}
    n_canon = len(CANONICAL_GENRES)
    for i, genre in enumerate(CANONICAL_GENRES):
        canon_indices[genre] = len(labels)
        labels.append(genre)
        colors.append(_CANONICAL_COLOR)
        hover.append(f"<b>{genre}</b><br>Art Findr canonical genre")
        node_x.append(col_x[0])
        node_y.append((i + 0.5) / n_canon)

    # -- Columns 1..N: museum values --
    # For each museum column, we need to:
    #   1. Collect all unique values used by this museum
    #   2. Position them vertically
    #   3. Create links from previous column's nodes
    #
    # "Previous column" for column 1 = canonical. For column 2+ = prior museum.
    # Links chain: for a given canonical genre, link its prev-column nodes
    # to this column's nodes.

    # Track which node indices each genre produced in each column.
    # genre_nodes[col_idx][genre] = list of node indices
    genre_nodes: list[dict[str, list[int]]] = [
        {g: [canon_indices[g]] for g in CANONICAL_GENRES}  # col 0
    ]

    for col_idx, (museum_key, museum_name, field_name, color) in enumerate(
        _MUSEUMS, start=1
    ):
        # Gather unique values in order of appearance
        seen: dict[str, int] = {}
        ordered_vals: list[str] = []
        genre_to_vals: dict[str, list[str]] = {}

        for genre in CANONICAL_GENRES:
            mapping = DEPARTMENT_MAP.get(genre, {})
            vals = _ensure_list(mapping.get(museum_key))
            genre_to_vals[genre] = vals
            for v in vals:
                if v not in seen:
                    seen[v] = 0  # placeholder, real index assigned below
                    ordered_vals.append(v)

        # Create nodes for this column
        n_vals = max(len(ordered_vals), 1)
        col_genre_nodes: dict[str, list[int]] = {g: [] for g in CANONICAL_GENRES}

        # Get field metadata for hover
        # MUSEUM_FIELD_MAP uses short labels — find the right key
        museum_label = _museum_label_key(museum_name)
        field_meta = MUSEUM_FIELD_MAP.get(museum_label, {}).get("genre", {})
        src_fields = ", ".join(field_meta.get("source_fields", []))
        match_str = field_meta.get("match", "")

        for i, v in enumerate(ordered_vals):
            idx = len(labels)
            seen[v] = idx
            labels.append(v)
            colors.append(color)
            hover.append(
                f"<b>{v}</b><br>"
                f"{museum_name}<br>"
                f"Field: <i>{field_name}</i><br>"
                f"Source field(s): {src_fields}<br>"
                f"Match: {match_str}"
            )
            node_x.append(col_x[col_idx])
            node_y.append((i + 0.5) / n_vals)

        # Assign genre→node mapping and create links from previous column
        prev_genre_nodes = genre_nodes[col_idx - 1]
        link_set: set[tuple[int, int]] = set()

        for genre in CANONICAL_GENRES:
            vals = genre_to_vals[genre]
            target_indices = [seen[v] for v in vals]
            col_genre_nodes[genre] = target_indices

            # Link from each prev-column node for this genre to each target
            for src_idx in prev_genre_nodes.get(genre, []):
                for tgt_idx in target_indices:
                    if (src_idx, tgt_idx) not in link_set:
                        link_set.add((src_idx, tgt_idx))
                        sources.append(src_idx)
                        targets.append(tgt_idx)
                        link_colors.append(_hex_to_rgba(color, 0.35))

        genre_nodes.append(col_genre_nodes)

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            pad=18,
            thickness=18,
            label=labels,
            color=colors,
            x=node_x,
            y=node_y,
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover,
        ),
        link=dict(
            source=sources,
            target=targets,
            value=[1] * len(sources),
            color=link_colors,
        ),
    ))
    fig.update_layout(
        font_size=11,
        height=max(700, n_canon * 65),
        margin=dict(l=200, r=150, t=10, b=10),
    )
    return fig


def build_medium_sankey() -> go.Figure:
    """Multi-column Sankey: Art Findr medium → per-museum keywords."""

    num_cols = 1 + len(_MUSEUMS)
    col_x = [i / (num_cols - 1) for i in range(num_cols)]
    col_x[0] = 0.001
    col_x[-1] = 0.999

    labels: list[str] = []
    colors: list[str] = []
    hover: list[str] = []
    node_x: list[float] = []
    node_y: list[float] = []
    sources: list[int] = []
    targets: list[int] = []
    link_colors: list[str] = []

    # Column 0: canonical media
    canon_indices: dict[str, int] = {}
    n_canon = len(CANONICAL_MEDIA)
    for i, medium in enumerate(CANONICAL_MEDIA):
        canon_indices[medium] = len(labels)
        labels.append(medium)
        colors.append(_CANONICAL_COLOR)
        hover.append(f"<b>{medium}</b><br>Art Findr canonical medium")
        node_x.append(col_x[0])
        node_y.append((i + 0.5) / n_canon)

    # medium_nodes[col_idx][medium] = list of node indices
    medium_nodes: list[dict[str, list[int]]] = [
        {m: [canon_indices[m]] for m in CANONICAL_MEDIA}
    ]

    medium_field_names = {
        "cma": "technique / type / department",
        "aic": "medium_display / classification_title",
        "moma": "Medium / Classification / Department",
    }

    for col_idx, (museum_key, museum_name, _, color) in enumerate(
        _MUSEUMS, start=1
    ):
        seen: dict[str, int] = {}
        ordered_kws: list[str] = []
        medium_to_kws: dict[str, list[str]] = {}

        for medium in CANONICAL_MEDIA:
            kws = MEDIUM_KEYWORD_MAP.get(medium, {}).get(museum_key, [])
            medium_to_kws[medium] = kws
            for kw in kws:
                if kw not in seen:
                    seen[kw] = 0
                    ordered_kws.append(kw)

        n_kws = max(len(ordered_kws), 1)
        col_medium_nodes: dict[str, list[int]] = {m: [] for m in CANONICAL_MEDIA}

        museum_label = _museum_label_key(museum_name)
        field_meta = MUSEUM_FIELD_MAP.get(museum_label, {}).get("medium", {})
        src_fields = ", ".join(field_meta.get("source_fields", []))
        match_str = field_meta.get("match", "keyword contains")
        field_name = medium_field_names.get(museum_key, "")

        for i, kw in enumerate(ordered_kws):
            idx = len(labels)
            seen[kw] = idx
            labels.append(kw)
            colors.append(color)
            hover.append(
                f"<b>{kw}</b><br>"
                f"{museum_name}<br>"
                f"Field: <i>{field_name}</i><br>"
                f"Source field(s): {src_fields}<br>"
                f"Match: {match_str}"
            )
            node_x.append(col_x[col_idx])
            node_y.append((i + 0.5) / n_kws)

        prev_medium_nodes = medium_nodes[col_idx - 1]
        link_set: set[tuple[int, int]] = set()

        for medium in CANONICAL_MEDIA:
            kws = medium_to_kws[medium]
            target_indices = [seen[kw] for kw in kws]
            col_medium_nodes[medium] = target_indices

            for src_idx in prev_medium_nodes.get(medium, []):
                for tgt_idx in target_indices:
                    if (src_idx, tgt_idx) not in link_set:
                        link_set.add((src_idx, tgt_idx))
                        sources.append(src_idx)
                        targets.append(tgt_idx)
                        link_colors.append(_hex_to_rgba(color, 0.35))

        medium_nodes.append(col_medium_nodes)

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(
            pad=18,
            thickness=18,
            label=labels,
            color=colors,
            x=node_x,
            y=node_y,
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover,
        ),
        link=dict(
            source=sources,
            target=targets,
            value=[1] * len(sources),
            color=link_colors,
        ),
    ))
    fig.update_layout(
        font_size=11,
        height=max(550, n_canon * 70),
        margin=dict(l=200, r=150, t=10, b=10),
    )
    return fig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _museum_label_key(full_name: str) -> str:
    """Map full museum name to the key used in MUSEUM_FIELD_MAP."""
    mapping = {
        "Cleveland Museum of Art": "CMA",
        "Art Institute of Chicago": "AIC",
        "Museum of Modern Art": "MoMA",
    }
    return mapping.get(full_name, full_name)
