# Open Access Art Finder

Art Findr is a React frontend backed by a FastAPI backend for exploring and downloading open-access artworks across major museums.

## Features

- **Multi-museum support**: Cleveland Museum of Art, Art Institute of Chicago, and MoMA
- **Extensible architecture**: Easy to add new museum adapters
- **Unified filtering**:
  - Orientation (Portrait/Landscape)
  - Genre/department (canonical mapping across museums)
  - Medium
  - Search term
  - Year range
- **Graceful error handling**: Filter feedback shows what worked vs. what was skipped
- **Human-readable filenames**: Downloads include museum code and artwork title

## Quick Start (React + FastAPI)

```bash
# Install backend deps
uv sync

# Run backend API
uv run uvicorn api:app --reload --port 8000
```

In a second terminal:

```bash
cd web
npm install
npm run dev
```

The React app runs at `http://localhost:5173` and proxies `/api/*` to the backend.

### Web tests

```bash
cd web
npm run test
npm run test:e2e
```

## How to Use

1. Select one or more museum sources.
2. Configure filters:
   - **Orientation**: Portrait or Landscape
   - **Genre / Medium**: Canonical values mapped across museums
   - **Search term**
   - **Year range**
3. Click **Load Artworks**.
4. Browse with **Back** / **Skip**, then download available images.

## Project Structure

```text
art_finder/
  adapters/           # Museum API adapters
  mappings/           # Cross-museum field/genre/medium mappings
  models.py           # Artwork, SearchFilters, AdapterResult
  services/           # Aggregation/search orchestration
api.py                # FastAPI backend for React app
web/                  # React + Tailwind + shadcn-style frontend
```

## API Endpoints

- FastAPI endpoints:
  - `GET /api/options`
  - `POST /api/search`
  - `GET /api/download`
  - `GET /api/help/mappings`
- React routes:
  - `/` main app
  - `/help` mapping reference

## Adding a New Museum

1. Create `art_finder/adapters/newmuseum.py`.
2. Implement `MuseumAdapter` subclass with `@register` decorator.
3. Add mapping entries to `art_finder/mappings/departments.py` (and related mapping metadata as needed).

## API Sources

- [Cleveland Museum of Art Open Access API](https://openaccess-api.clevelandart.org/)
- [Art Institute of Chicago API](https://api.artic.edu/)
- [MoMA Collection Data](https://github.com/MuseumofModernArt/collection)

## License

Artwork images are provided under various open access licenses (CC0, Public Domain, etc.) by their museums. Check each artwork's metadata for licensing specifics.
