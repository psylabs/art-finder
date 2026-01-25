# Cleveland Museum Portrait Reviewer

A simple Streamlit app to review and download portrait-oriented artworks from the Cleveland Museum of Art, filtered by select departments.

## Features

- 🎨 Filters by department (Indian/Southeast Asian, Islamic, Modern European, American Painting, Prints, Drawings)
- 🖼️ Automatically filters for portrait orientation (height > width)
- 📋 Shows artwork metadata (title, artist, date, technique, department, classification)
- ⬇️ Single-click download with human-readable filenames (Title - Artist)
- ⬅️ Back button to review previous images
- ⏭️ Skip button to move forward
- 💻 Optimized image size for laptop screens (no scrolling needed)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

## How to Use

1. Click "Load Portrait Artworks" to fetch artworks from select departments
2. Review each artwork and its metadata
3. Use "Back" to go to previous artworks, "Skip" to move forward
4. Click "Download" once to save the high-res image with readable filename (auto-advances to next)

## API Source

Images are from the [Cleveland Museum of Art Open Access API](https://openaccess-api.clevelandart.org/)

