import os
import requests
from dotenv import load_dotenv
from rapidfuzz import fuzz

load_dotenv()

# LASTFM_API_KEY must be set as an environment variable before running
LASTFM_KEY = os.environ.get("LASTFM_API_KEY")
LASTFM_BASE = "http://ws.audioscrobbler.com/2.0/"


def _get(params: dict) -> dict | None:
    if not LASTFM_KEY:
        print("[matcher] LASTFM_API_KEY is not set")
        return None
    try:
        resp = requests.get(
            LASTFM_BASE,
            params={**params, "api_key": LASTFM_KEY, "format": "json"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[matcher] request error: {e}")
        return None


def get_similar_artists(artist_name: str, limit: int = 100) -> list[dict]:
    data = _get({"method": "artist.getSimilar", "artist": artist_name, "limit": limit})
    if not data:
        return []
    try:
        similar = data["similarartists"]["artist"]
        return [{"name": a["name"], "match": float(a["match"])} for a in similar]
    except (KeyError, TypeError):
        return []


def get_artist_tags(artist_name: str) -> list[str]:
    data = _get({"method": "artist.getTopTags", "artist": artist_name})
    if not data:
        return []
    try:
        tags = data["toptags"]["tag"]
        return [t["name"] for t in tags[:3]]
    except (KeyError, TypeError):
        return []


def _get_listener_data(artist_name: str) -> tuple[int, str]:
    """Returns (raw_count, formatted_string). raw_count is 0 when unknown."""
    data = _get({"method": "artist.getInfo", "artist": artist_name})
    if not data:
        return 0, "Unknown"
    try:
        count = int(data["artist"]["stats"]["listeners"])
    except (KeyError, TypeError, ValueError):
        return 0, "Unknown"

    if count < 1_000:
        return count, f"{count} listeners"
    if count < 1_000_000:
        return count, f"{count / 1_000:.1f}K listeners"
    return count, f"{count / 1_000_000:.1f}M listeners"


def get_artist_listeners(artist_name: str) -> str:
    _, formatted = _get_listener_data(artist_name)
    return formatted


def fuzzy_match(similar_artists: list[dict], lineup: list[str]) -> list[dict]:
    matches = []
    for similar in similar_artists:
        s_name = similar["name"]
        s_lower = s_name.lower()
        for lineup_artist in lineup:
            la_lower = lineup_artist.lower()
            if len(s_name) <= 4:
                # Short names must match exactly to prevent "War", "Lady" false positives
                if s_lower != la_lower:
                    continue
                score = 100
            else:
                score = fuzz.WRatio(s_lower, la_lower)
                if score < 80:
                    continue
            matches.append({
                "name": lineup_artist,
                "match": round(similar["match"] * 100),
                "similarity_score": score,
            })
            break
    return matches


def get_recommendations(seed_artist: str, lineup: list[str]) -> list[dict]:
    similar = get_similar_artists(seed_artist, limit=100)
    matches = fuzzy_match(similar, lineup)

    # Expand if fewer than 3 matches: get similar artists for top 3 similar artists
    if len(matches) < 3 and similar:
        expanded = {a["name"]: a["match"] for a in similar}
        for neighbor in similar[:3]:
            for a in get_similar_artists(neighbor["name"], limit=50):
                if a["name"] not in expanded:
                    expanded[a["name"]] = a["match"] * neighbor["match"]
        merged = [{"name": n, "match": s} for n, s in expanded.items()]
        matches = fuzzy_match(merged, lineup)

    # Deduplicate by lineup artist name, keeping highest match score
    seen: dict[str, dict] = {}
    for m in matches:
        if m["name"] not in seen or m["match"] > seen[m["name"]]["match"]:
            seen[m["name"]] = m
    matches = list(seen.values())

    # Enrich with tags and listeners; drop non-artists with fewer than 500 listeners
    results = []
    for m in matches:
        count, listeners = _get_listener_data(m["name"])
        if count > 0 and count < 500:
            continue
        results.append({
            "name": m["name"],
            "match": m["match"],
            "tags": get_artist_tags(m["name"]),
            "listeners": listeners,
        })

    results.sort(key=lambda x: x["match"], reverse=True)

    # Rescale after filtering: top result is always 100%, others proportional
    if results:
        top = results[0]["match"] or 1
        for r in results:
            r["match"] = round(r["match"] / top * 100)

    return results


if __name__ == "__main__":
    from scraper import get_lineup

    SEED = "Arctic Monkeys"
    FESTIVAL = "Glastonbury Festival 2023"

    print(f"Scraping lineup for: {FESTIVAL}")
    lineup = get_lineup(FESTIVAL)
    print(f"Lineup has {len(lineup)} artists\n")

    print(f"Seed artist: {SEED}\n")
    results = get_recommendations(SEED, lineup)
    if results:
        print(f"Found {len(results)} matches:\n")
        for r in results:
            tags = ", ".join(r["tags"]) if r["tags"] else "—"
            print(f"  {r['name']:<35} match={r['match']:>3}%  {r['listeners']:<20}  [{tags}]")
    else:
        print("No matches found.")
