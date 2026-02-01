# Open Access Art Finder

A Streamlit app to discover and download open access artworks from museum APIs.

## Features

- **Multi-museum support**: Currently supports Cleveland Museum of Art and Art Institute of Chicago
- **Extensible architecture**: Easy to add new museum adapters
- **Unified filtering**:
  - Orientation (Portrait/Landscape)
  - Department (with cross-museum mapping)
  - Year range
  - Minimum resolution
- **Graceful error handling**: Filter feedback shows what worked vs. what was skipped
- **Human-readable filenames**: Downloads include museum code and artwork title

## Quick Start

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync dependencies
uv sync

# Run the app
uv run streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

## How to Use

1. Select a museum source in the sidebar
2. Configure filters:
   - **Orientation**: Portrait or Landscape
   - **Department**: Filter by curatorial area (canonical names work across museums)
   - **Year Range**: Filter by creation date
   - **Resolution**: Minimum image dimensions
3. Click "Load Artworks" to fetch
4. Review artworks and download your favorites

## Project Structure

```
art_finder/
  adapters/           # Museum API adapters
    base.py           # Abstract MuseumAdapter class
    cma.py            # Cleveland Museum of Art
    aic.py            # Art Institute of Chicago
  mappings/
    departments.py    # Cross-museum department mapping
  models.py           # Artwork, SearchFilters, AdapterResult
app.py                # Streamlit UI
```

## Adding a New Museum

1. Create `art_finder/adapters/newmuseum.py`
2. Implement `MuseumAdapter` subclass with `@register` decorator
3. Add department mappings to `art_finder/mappings/departments.py`

See existing adapters for examples.

## API Sources

- [Cleveland Museum of Art Open Access API](https://openaccess-api.clevelandart.org/)
- [Art Institute of Chicago API](https://api.artic.edu/)

## License

The artwork images are provided under various open access licenses (CC0, Public Domain) by the respective museums. Please check individual artwork metadata for specific licensing terms.
