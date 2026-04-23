import asyncio
import re

import httpx

TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_KEYWORD_SEARCH_URL = "https://api.themoviedb.org/3/search/keyword"
TMDB_DISCOVER_URL = "https://api.themoviedb.org/3/discover/movie"
TMDB_EXTERNAL_IDS_URL = "https://api.themoviedb.org/3/movie/{tmdb_id}/external_ids"
TMDB_DETAILS_URL = "https://api.themoviedb.org/3/movie/{tmdb_id}"
POSTER_BASE = "https://image.tmdb.org/t/p/w500"
TMDB_DELAY = 0.3

GENRE_MAP: dict[str, int] = {
    "action": 28,
    "comedy": 35,
    "sci-fi": 878,
    "science fiction": 878,
    "thriller": 53,
    "drama": 18,
    "horror": 27,
    "romance": 10749,
    "animation": 16,
    "crime": 80,
    "adventure": 12,
}

DECADE_RE = re.compile(r"\b((?:19|20)\d0s|\d0s)\b", re.IGNORECASE)


def _decade_to_date_range(decade: str | None) -> tuple[str | None, str | None]:
    if not decade:
        return None, None
    m = DECADE_RE.search(decade)
    if not m:
        return None, None
    token = m.group(1).lower().replace("s", "")
    if len(token) == 2:
        token = ("20" if int(token) < 30 else "19") + token
    start_year = int(token)
    return f"{start_year}-01-01", f"{start_year + 9}-12-31"


async def _tmdb_search(client: httpx.AsyncClient, title: str, token: str) -> list[dict]:
    resp = await client.get(
        TMDB_SEARCH_URL,
        params={"query": title, "language": "en-US", "page": 1},
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("results", [])[:5]


async def _resolve_keywords(
    client: httpx.AsyncClient, keywords: list[str], token: str
) -> list[int]:
    ids: list[int] = []
    for i, kw in enumerate(keywords):
        if i > 0:
            await asyncio.sleep(TMDB_DELAY)
        try:
            resp = await client.get(
                TMDB_KEYWORD_SEARCH_URL,
                params={"query": kw},
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if results:
                ids.append(results[0]["id"])
        except httpx.HTTPError:
            pass
    return ids


async def _tmdb_discover(
    client: httpx.AsyncClient,
    genre_ids: list[int],
    keyword_ids: list[int],
    decade: str | None,
    token: str,
) -> list[dict]:
    date_gte, date_lte = _decade_to_date_range(decade)

    params: dict = {
        "language": "en-US",
        "sort_by": "vote_average.desc",
        "vote_count.gte": 150,
    }
    if genre_ids:
        params["with_genres"] = ",".join(str(gid) for gid in genre_ids)
    if keyword_ids:
        params["with_keywords"] = "|".join(str(kid) for kid in keyword_ids)
    if date_gte:
        params["primary_release_date.gte"] = date_gte
    if date_lte:
        params["primary_release_date.lte"] = date_lte

    resp = await client.get(
        TMDB_DISCOVER_URL,
        params=params,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("results", [])[:15]


async def _tmdb_external_ids(
    client: httpx.AsyncClient, tmdb_id: int, token: str
) -> dict:
    resp = await client.get(
        TMDB_EXTERNAL_IDS_URL.format(tmdb_id=tmdb_id),
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


async def _tmdb_details(
    client: httpx.AsyncClient, tmdb_id: int, token: str
) -> dict:
    resp = await client.get(
        TMDB_DETAILS_URL.format(tmdb_id=tmdb_id),
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()
