# Project Brief — festival-discover

Read this entire document before writing any code. This is the complete spec for a festival artist discovery web app.

---

## What this app does

A user inputs a festival name and an artist they already like. The app finds other artists on that festival's lineup that the user would probably enjoy, based on musical similarity data from Last.fm.

**Core flow:**
1. User types a festival name (e.g. "Coachella 2024")
2. User types an artist they like (e.g. "Kaytranada") — this artist does NOT need to be on the lineup, they are just a taste reference
3. App scrapes the festival lineup from Wikipedia
4. App queries Last.fm for artists similar to the seed artist
5. App fuzzy-matches the similar artists list against the festival lineup
6. App returns a ranked list of festival artists the user would probably enjoy, sorted by similarity score

---

## File structure

```
festival-discover/
├── app.py               ← Flask backend, serves API endpoints and static files
├── scraper.py           ← Wikipedia lineup scraper
├── matcher.py           ← Last.fm API calls + fuzzy matching logic
├── requirements.txt     ← Python dependencies (already filled in)
├── README.md            ← already exists
└── static/
    ├── index.html       ← frontend UI
    ├── style.css        ← all styles
    └── script.js        ← frontend logic, API calls, rendering
```

---

## Tech stack

- **Backend:** Python 3.12, Flask
- **Scraping:** requests, BeautifulSoup4
- **Fuzzy matching:** rapidfuzz
- **API:** Last.fm (free, no auth required for artist.getSimilar)
- **Frontend:** vanilla HTML, CSS, JavaScript — no frameworks
- **Deployment:** Flask backend on Render.com free tier, or run locally

---

## Backend — app.py

Flask app with two endpoints:

### GET /api/lineup?festival=Coachella+2024
- Calls `scraper.get_lineup(festival_name)`
- Returns JSON: `{ "festival": "Coachella 2024", "artists": ["Artist1", "Artist2", ...] }`
- Returns 400 if festival param is missing
- Returns 404 with error message if scraper returns empty list

### POST /api/discover
- Request body JSON: `{ "festival": "Coachella 2024", "seed_artist": "Kaytranada" }`
- Calls `scraper.get_lineup()` to get festival artists
- Calls `matcher.get_recommendations()` to get ranked matches
- Returns JSON: `{ "festival": "Coachella 2024", "seed_artist": "Kaytranada", "results": [ { "name": "Jungle", "match": 91, "tags": ["funk", "soul"], "listeners": "890K" }, ... ] }`
- Returns 400 if required fields missing
- Returns 404 if no matches found

### Static file serving
Flask should serve `static/index.html` at the root `/` route.

### CORS
Add CORS headers to all API responses so the frontend can call the API from any origin during development:
```python
@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response
```

---

## Scraper — scraper.py

### Function: `get_lineup(festival_name) → list[str]`

Scrapes Wikipedia for the festival lineup. Returns a cleaned list of artist name strings.

**How it works:**
1. Construct Wikipedia URL: `https://en.wikipedia.org/wiki/{festival_name.replace(' ', '_')}`
2. Fetch with requests, User-Agent header set to `"festival-discover/1.0"`
3. Parse with BeautifulSoup
4. Extract artist names from `<li>`, `<td>`, and `<dd>` tags
5. Clean and filter the results

**Filtering rules — skip any text that:**
- Is fewer than 3 characters or more than 60 characters
- Contains any of these words (case-insensitive): "festival", "stage", "day ", "weekend", "presented", "sponsored", "tickets", "lineup", "http", "wiki", "citation", "archived", "retrieved", "isbn", "pp.", "vol."
- Is purely numeric
- Contains bracket notation like "[1]" or "(2024)"

**Cleaning rules:**
- Strip whitespace
- Remove text in parentheses: "Artist Name (DJ set)" → "Artist Name"
- Remove text after " – " or " - " if it looks like a description
- Deduplicate (use a set)

**Return:** list of cleaned artist name strings. Empty list if fetch fails or page not found.

**Error handling:** Wrap the request in try/except, return empty list on any exception. Print the error for debugging.

---

## Matcher — matcher.py

### Last.fm API

Base URL: `http://ws.audioscrobbler.com/2.0/`
API key: `f5f1e3a6b2c4d8e9a7b3c5d1e2f4a6b8` — use this placeholder, the real key will be substituted as an environment variable `LASTFM_API_KEY`. Read it with `os.environ.get('LASTFM_API_KEY', 'YOUR_KEY_HERE')`.

Actually — do NOT hardcode any API key. Use `os.environ.get('LASTFM_API_KEY')` and note in comments that the key must be set as an environment variable.

### Function: `get_similar_artists(artist_name, limit=100) → list[dict]`

Calls Last.fm `artist.getSimilar` endpoint.

```
GET http://ws.audioscrobbler.com/2.0/?method=artist.getSimilar&artist={artist_name}&limit={limit}&api_key={key}&format=json
```

Returns list of dicts:
```python
[
    { "name": "Four Tet", "match": 0.91 },
    { "name": "Kaytranada", "match": 0.84 },
    ...
]
```

Match score is a float 0-1 from Last.fm. Return empty list on any error.

### Function: `get_artist_tags(artist_name) → list[str]`

Calls Last.fm `artist.getTopTags` endpoint.

```
GET http://ws.audioscrobbler.com/2.0/?method=artist.getTopTags&artist={artist_name}&api_key={key}&format=json
```

Returns top 3 tag names as a list of strings. Return empty list on error.

### Function: `get_artist_listeners(artist_name) → str`

Calls Last.fm `artist.getInfo` endpoint.

```
GET http://ws.audioscrobbler.com/2.0/?method=artist.getInfo&artist={artist_name}&api_key={key}&format=json
```

Returns listener count formatted as a readable string:
- Under 1000: "< 1K listeners"
- 1000-999999: "X.XK listeners" (e.g. "340K listeners")
- 1M+: "X.XM listeners" (e.g. "2.1M listeners")

Return "Unknown" on error.

### Function: `fuzzy_match(similar_artists, lineup) → list[dict]`

Takes the similar artists list and the festival lineup list. Returns only the similar artists whose names fuzzy-match a lineup artist above an 85% threshold.

```python
from rapidfuzz import fuzz

def fuzzy_match(similar_artists, lineup):
    matches = []
    for similar in similar_artists:
        for lineup_artist in lineup:
            score = fuzz.ratio(similar['name'].lower(), lineup_artist.lower())
            if score >= 85:
                matches.append({
                    'name': lineup_artist,  # use the lineup version of the name
                    'match': round(similar['match'] * 100),  # convert to 0-100 integer
                    'similarity_score': score
                })
                break
    return matches
```

### Function: `get_recommendations(seed_artist, lineup) → list[dict]`

Main function that orchestrates everything.

1. Call `get_similar_artists(seed_artist, limit=100)`
2. Call `fuzzy_match(similar_artists, lineup)`
3. If matches < 3: expand by getting similar artists for the top 3 similar artists, merge results, deduplicate, re-run fuzzy match
4. For each match, call `get_artist_tags()` and `get_artist_listeners()`
5. Sort by match score descending
6. Return list of dicts:
```python
[
    {
        "name": "Jungle",
        "match": 91,
        "tags": ["funk", "soul", "electronic"],
        "listeners": "890K listeners"
    },
    ...
]
```

Return empty list if no matches found after expansion.

---

## Frontend — static/index.html, style.css, script.js

### Visual design

Match the aesthetic established in the mockup:
- Background: `#FAF8F4` (warm cream)
- Text primary: `#1A1A1A`
- Text secondary: `#555`
- Text muted: `#888`
- Accent: `#C84B0F` (burnt orange)
- Accent light: `#FDEEE5`
- Border: `#E0DAD0`
- Font: Inter from Google Fonts (weights 400, 500)

### Layout — index.html

```
<header>        ← logo "festival.discover" + "Powered by Last.fm" tag
<main>
  <section class="hero">     ← eyebrow, title, description
  <section class="inputs">   ← festival input, artist input, discover button (stacked vertically)
  <hr>
  <section class="results">  ← empty state OR results grid
<footer>        ← "Built by Kyle Wong" left, "Data from Last.fm & Wikipedia" right
```

### Input section

Two text inputs stacked vertically, full width up to 480px, then a "Discover artists" button below. Stacked layout (not side by side) to avoid the button being cut off on smaller screens.

- Festival input: placeholder "e.g. Coachella 2024"
- Artist input: placeholder "e.g. Kaytranada"
- Button: burnt orange, full width of inputs

### Empty state

When no search has been run yet, show a centered icon (magnifying glass SVG), a title "Enter a festival and an artist to get started", and a subtitle "We'll find who on the lineup you'll probably enjoy."

### Loading state

When the API call is in progress, show a simple loading indicator — the button text changes to "Discovering..." and is disabled. A subtle spinner or pulsing text below the inputs.

### Results state

After successful search:

**Seed pill:** Small dark pill showing "Based on: {seed_artist}" with a burnt orange dot

**Results header:** "{X} artists found at {festival}" on the left, artist count on the right

**Results grid:** 2 columns on desktop, 1 column on mobile. Each card:
- Artist name (14px, weight 500)
- Match percentage badge (burnt orange pill, top right)
- Match bar (thin progress bar, 0-100% width based on match score)
- Genre tags (small pills, muted background)
- Listener count (small, muted)
- Hover: border changes to accent color

**No results state:** If API returns empty results, show "No matches found. Try a different artist or festival." with a suggestion to try a more mainstream seed artist.

**Error state:** If API call fails, show "Something went wrong. Please try again." in muted text.

### script.js

```javascript
// On "Discover artists" button click:
// 1. Validate inputs — both must be non-empty
// 2. Set loading state
// 3. POST to /api/discover with { festival, seed_artist }
// 4. On success: render results
// 5. On error: show error state
// 6. Always: restore button state

async function discover() {
    const festival = document.getElementById('festival-input').value.trim();
    const seedArtist = document.getElementById('artist-input').value.trim();
    
    if (!festival || !seedArtist) {
        // show validation message
        return;
    }
    
    // set loading state
    // fetch /api/discover
    // render results or error
}
```

Results rendering: dynamically build card HTML for each result and inject into the results container. No frameworks.

---

## Known limitations (document these in README)

- Wikipedia scraping is imperfect — festival pages vary in structure. Works best for major festivals with well-structured Wikipedia articles (Coachella, Glastonbury, Lollapalooza, EDC, Tomorrowland, etc.)
- B2B sets and supergroup aliases (e.g. "Anti Up" = Chris Lake + Chris Lorenzo) are not resolved — they appear as-is on the lineup and may not match Last.fm data
- Last.fm similarity data reflects online listening patterns and may not perfectly capture live performance style
- Fuzzy matching threshold of 85% catches most name variations but very different spellings may be missed

---

## Build order

Build and test in this exact order:

1. `scraper.py` — test standalone with `python3 scraper.py` for a known festival
2. `matcher.py` — test standalone with `python3 matcher.py` for a known artist + small lineup
3. `app.py` — wire scraper and matcher into Flask endpoints, test with curl or Postman
4. `static/index.html` + `style.css` — build full UI skeleton
5. `static/script.js` — wire frontend to Flask API, test end to end locally
6. Final pass: error handling, loading states, mobile responsiveness
7. Deploy to Render

---

## Environment variables

- `LASTFM_API_KEY` — required, must be set before running. Get a free key at last.fm/api

---

## Important rules

- No hardcoded API keys anywhere in code
- No Bootstrap, no jQuery, no frontend frameworks
- All colors via CSS custom properties
- Keep each Python file focused on its single responsibility
- Handle all API errors gracefully — never let an exception reach the user
- Mobile responsive — inputs and results grid stack to single column below 768px
- Test each file standalone before wiring everything together
