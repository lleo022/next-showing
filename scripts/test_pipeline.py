"""
Pipeline integration test: parse → TMDB search → OMDb enrichment.

Run from the project root:
    uv run python scripts/test_pipeline.py
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PARSE_URL = "http://localhost:8000/parse"
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_EXTERNAL_IDS_URL = "https://api.themoviedb.org/3/movie/{tmdb_id}/external_ids"
OMDB_URL = "http://www.omdbapi.com/"
POSTER_BASE = "https://image.tmdb.org/t/p/w500"
TMDB_DELAY = 0.3  # seconds between search calls

DATA_DIR = Path(__file__).parent.parent / "data"
WATCHED_CSV = DATA_DIR / "watched.csv"
RATINGS_CSV = DATA_DIR / "ratings.csv"

DIVIDER = "─" * 36


# ---------------------------------------------------------------------------
# Step 1 — Parse
# ---------------------------------------------------------------------------

async def fetch_profile(client: httpx.AsyncClient) -> dict:
    with open(WATCHED_CSV, "rb") as wf, open(RATINGS_CSV, "rb") as rf:
        response = await client.post(
            PARSE_URL,
            files={
                "watched_file": ("watched.csv", wf, "text/csv"),
                "ratings_file": ("ratings.csv", rf, "text/csv"),
            },
            timeout=30,
        )
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Step 3 — TMDB search
# ---------------------------------------------------------------------------

async def tmdb_search(client: httpx.AsyncClient, title: str, year: int) -> dict | None:
    token = os.getenv("TMDB_API_KEY")
    if not token:
        raise RuntimeError("TMDB_API_KEY not set in environment")

    resp = await client.get(
        TMDB_SEARCH_URL,
        params={"query": title, "year": year},
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if not results:
        return None

    top = results[0]
    poster_path = top.get("poster_path") or ""
    return {
        "tmdb_id": top.get("id"),
        "title": top.get("title"),
        "year": (top.get("release_date") or "")[:4],
        "overview": top.get("overview"),
        "poster_path": poster_path,
        "poster_url": f"{POSTER_BASE}{poster_path}" if poster_path else None,
    }


async def tmdb_external_ids(client: httpx.AsyncClient, tmdb_id: int) -> dict:
    token = os.getenv("TMDB_API_KEY")
    resp = await client.get(
        TMDB_EXTERNAL_IDS_URL.format(tmdb_id=tmdb_id),
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Step 4 — OMDb enrichment
# ---------------------------------------------------------------------------

async def omdb_enrich(client: httpx.AsyncClient, imdb_id: str) -> dict:
    api_key = os.getenv("OMDB_API_KEY")
    if not api_key:
        raise RuntimeError("OMDB_API_KEY not set in environment")

    resp = await client.get(
        OMDB_URL,
        params={"i": imdb_id, "apikey": api_key},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    rt_score = next(
        (r["Value"] for r in data.get("Ratings", []) if r.get("Source") == "Rotten Tomatoes"),
        None,
    )
    return {
        "imdb_rating": data.get("imdbRating"),
        "metascore": data.get("Metascore"),
        "rotten_tomatoes": rt_score,
        "ratings": data.get("Ratings", []),
    }


# ---------------------------------------------------------------------------
# Enrich one movie: TMDB + OMDb concurrently where possible
# ---------------------------------------------------------------------------

async def enrich_movie(
    client: httpx.AsyncClient,
    entry: dict,
) -> tuple[dict | None, str | None]:
    """
    Returns (result_dict, error_message).
    result_dict is None on failure; error_message is None on success.
    """
    title = entry["title"]
    year = entry["year"]
    my_rating = entry.get("rating")

    tmdb = await tmdb_search(client, title, year)
    if not tmdb:
        return None, f"no TMDB results for '{title}' ({year})"

    # Fetch external IDs (need imdb_id before OMDb call)
    ext_ids = await tmdb_external_ids(client, tmdb["tmdb_id"])
    imdb_id = ext_ids.get("imdb_id")

    omdb = {}
    if imdb_id:
        omdb = await omdb_enrich(client, imdb_id)
    else:
        omdb = {"imdb_rating": None, "metascore": None, "rotten_tomatoes": None}

    return {
        "title": tmdb["title"],
        "year": tmdb["year"],
        "my_rating": my_rating,
        "tmdb_id": tmdb["tmdb_id"],
        "imdb_id": imdb_id,
        "poster": tmdb["poster_url"],
        "imdb_rating": omdb.get("imdb_rating"),
        "metascore": omdb.get("metascore"),
        "rotten_tomatoes": omdb.get("rotten_tomatoes"),
    }, None


# ---------------------------------------------------------------------------
# Step 5 — Print result block
# ---------------------------------------------------------------------------

def print_result(result: dict) -> None:
    print(DIVIDER)
    print(f"{'Title':<11}: {result['title']}")
    print(f"{'Year':<11}: {result['year']}")
    print(f"{'My Rating':<11}: {result['my_rating']}")
    print(f"{'TMDB ID':<11}: {result['tmdb_id']}")
    print(f"{'IMDB ID':<11}: {result['imdb_id'] or 'N/A'}")
    print(f"{'Poster':<11}: {result['poster'] or 'N/A'}")
    print(f"{'IMDB':<11}: {result['imdb_rating'] or 'N/A'}")
    print(f"{'Metascore':<11}: {result['metascore'] or 'N/A'}")
    print(f"{'Rotten T.':<11}: {result['rotten_tomatoes'] or 'N/A'}")
    print(DIVIDER)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    # --- Step 1: Parse ---
    async with httpx.AsyncClient() as client:
        try:
            profile = await fetch_profile(client)
        except httpx.ConnectError:
            print("ERROR: Could not connect to http://localhost:8000 — is the server running?")
            sys.exit(1)

    watched = profile.get("watched", [])
    rated = profile.get("rated", [])
    errors = profile.get("parse_errors", [])
    print(f"Parsed {len(watched)} watched, {len(rated)} rated, {len(errors)} errors")

    # --- Step 2: Pick 3 movies ---
    candidates = [m for m in rated if m.get("title") and m.get("year")][:3]
    if not candidates:
        print("ERROR: No rated movies with title and year found.")
        sys.exit(1)

    print()
    for m in candidates:
        print(f"  {m['title']} ({m['year']}) — {m['rating']} stars")
    print()

    # --- Steps 3-4: Enrich each movie (with delay between TMDB searches) ---
    results: list[dict | None] = []
    failures: list[tuple[str, str]] = []

    async with httpx.AsyncClient() as client:
        for i, entry in enumerate(candidates):
            if i > 0:
                await asyncio.sleep(TMDB_DELAY)

            label = f"{entry['title']} ({entry['year']})"
            try:
                result, err = await enrich_movie(client, entry)
            except Exception as exc:
                result, err = None, str(exc)

            if result:
                results.append(result)
            else:
                print(f"WARNING: skipping {label} — {err}")
                failures.append((label, err or "unknown error"))

    # --- Step 5: Print blocks ---
    print()
    for result in results:
        print_result(result)

    # --- Step 6: Summary ---
    total = len(candidates)
    success = len(results)
    print(f"\n{success}/{total} movies successfully enriched")
    if failures:
        print("Failed:")
        for label, reason in failures:
            print(f"  - {label}: {reason}")


if __name__ == "__main__":
    asyncio.run(main())
