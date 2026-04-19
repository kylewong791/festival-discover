import re
import requests
from bs4 import BeautifulSoup

SKIP_WORDS = [
    "festival", "stage", "day ", "weekend", "presented", "sponsored",
    "tickets", "lineup", "http", "wiki", "citation", "archived",
    "retrieved", "isbn", "pp.", "vol.", "glastonbury", "lollapalooza",
    "coachella", "tomorrowland", "bonnaroo", "bbc ", "tour", "radio",
    "sign language", "sign-language", "hope is a dangerous thing",
]

# Wikipedia namespaces to exclude from link harvesting
_WIKI_NS = re.compile(r'^/wiki/(Wikipedia|File|Category|Help|Portal|Special|Talk|User|Template):')


def _clean(text):
    text = text.strip()
    text = re.sub(r'\s*\(.*?\)\s*$', '', text).strip()
    text = re.sub(r'\s+[–\-]\s+.*$', '', text).strip()
    text = re.sub(r'\s*\[[^\]]{1,3}\]\s*$', '', text).strip()
    text = re.sub(r'\s+\d{1,2}:\d{2}.*$', '', text).strip()
    return text


def _is_valid(text):
    if len(text) < 3 or len(text) > 60:
        return False
    low = text.lower()
    if any(word in low for word in SKIP_WORDS):
        return False
    if text.isdigit():
        return False
    if re.search(r'\[\w+\]|\(\d{4}\)', text):
        return False
    if re.search(r'\b(January|February|March|April|May|June|July|August|'
                 r'September|October|November|December|\d{4})\b', text):
        return False
    if re.match(r'^\d', text):
        return False
    # "City, Country" or "City, State" geographic patterns
    if re.search(r',\s+[A-Z]', text):
        return False
    return True


def _harvest_links(content) -> list[str]:
    """Extract artist names from internal Wikipedia <a> links inside lineup containers."""
    seen: set[str] = set()
    artists: list[str] = []
    # Only look at links inside table cells and list items — where lineups live
    containers = content.find_all(["td", "li", "dd"])
    for container in containers:
        if container.find_parent(id="toc") or container.find_parent(class_="toc"):
            continue
        for a in container.find_all("a", href=True):
            href = a["href"]
            if not href.startswith("/wiki/"):
                continue
            if _WIKI_NS.match(href):
                continue
            name = _clean(a.get_text(strip=True))
            if name and _is_valid(name) and name not in seen:
                seen.add(name)
                artists.append(name)
    return artists


def _harvest_lists(content) -> list[str]:
    """Fallback: extract artist names from <li>/<dd> text for text-only lineups."""
    seen: set[str] = set()
    artists: list[str] = []
    for tag in content.find_all(["li", "dd"]):
        if tag.find_parent(id="toc") or tag.find_parent(class_="toc"):
            continue
        raw = tag.get_text(separator=" ", strip=True)
        for part in re.split(r'[•·/|]', raw):
            name = _clean(part)
            if name and _is_valid(name) and name not in seen:
                seen.add(name)
                artists.append(name)
    return artists


def _search_wikipedia(query: str) -> str | None:
    """Returns the best-matching Wikipedia page title via opensearch, or None."""
    try:
        resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "opensearch", "search": query, "limit": 5, "format": "json"},
            headers={"User-Agent": "festival-discover/1.0"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        # Response: [query, [titles], [descriptions], [urls]]
        urls = data[3]
        if urls:
            # Extract clean title from URL: ".../wiki/Glastonbury_Festival_2023" → "Glastonbury Festival 2023"
            return urls[0].split("/wiki/")[-1].replace("_", " ")
    except Exception as e:
        print(f"[scraper] search error: {e}")
    return None


def get_lineup(festival_name: str) -> list[str]:
    page_title = _search_wikipedia(festival_name)
    if page_title:
        print(f"[scraper] resolved '{festival_name}' → '{page_title}'")
        slug = page_title.replace(" ", "_")
    else:
        slug = festival_name.replace(" ", "_")

    url = f"https://en.wikipedia.org/wiki/{slug}"
    try:
        resp = requests.get(url, headers={"User-Agent": "festival-discover/1.0"}, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"[scraper] fetch error: {e}")
        return []

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        content = soup.find("div", class_="mw-parser-output")
        if not content:
            content = soup.find("div", id="mw-content-text") or soup

        artists = _harvest_links(content)

        # If link harvesting found very few results, fall back to text extraction
        if len(artists) < 10:
            artists = _harvest_lists(content)

        return artists
    except Exception as e:
        print(f"[scraper] parse error: {e}")
        return []


if __name__ == "__main__":
    for festival in ["Glastonbury Festival 2023", "Glastonbury Festival 2024"]:
        print(f"\nScraping: {festival}")
        lineup = get_lineup(festival)
        print(f"Found {len(lineup)} artists")
        for a in lineup[:20]:
            print(f"  {a}")
        if len(lineup) > 20:
            print(f"  ... and {len(lineup) - 20} more")
