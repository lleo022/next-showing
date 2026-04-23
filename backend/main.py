import asyncio
import json
import re
import tempfile
import os
from pathlib import Path

import anthropic
import httpx
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from lb_parser import build_user_profile, UserProfile

from dotenv import load_dotenv
load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# /parse

@app.post("/parse", response_model=UserProfile)
async def parse(
    watched_file: UploadFile = File(...),
    ratings_file: UploadFile | None = File(None),
):
    watched_tmp = None
    ratings_tmp = None

    try:
        # Save watched_file to a temp file
        try:
            content = await watched_file.read()
            if not content:
                raise HTTPException(status_code=400, detail="watched_file is empty or unreadable")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as f:
                f.write(content)
                watched_tmp = f.name
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not read watched_file: {e}")

        # Save ratings_file to a temp file if provided
        if ratings_file is not None:
            try:
                ratings_content = await ratings_file.read()
                if ratings_content:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as f:
                        f.write(ratings_content)
                        ratings_tmp = f.name
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Could not read ratings_file: {e}")

        profile = build_user_profile(
            Path(watched_tmp),
            Path(ratings_tmp) if ratings_tmp else None,
        )
        return profile

    finally:
        if watched_tmp and os.path.exists(watched_tmp):
            os.unlink(watched_tmp)
        if ratings_tmp and os.path.exists(ratings_tmp):
            os.unlink(ratings_tmp)



# /recommend

TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_KEYWORD_SEARCH_URL = "https://api.themoviedb.org/3/search/keyword"
TMDB_DISCOVER_URL = "https://api.themoviedb.org/3/discover/movie"
TMDB_EXTERNAL_IDS_URL = "https://api.themoviedb.org/3/movie/{tmdb_id}/external_ids"
TMDB_DETAILS_URL = "https://api.themoviedb.org/3/movie/{tmdb_id}"
OMDB_URL = "http://www.omdbapi.com/"
OLLAMA_URL = "http://localhost:11434/api/generate"
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


class WatchedFilm(BaseModel):
    title: str
    year: int | None = None


class RecommendRequest(BaseModel):
    request: str
    watched: list[WatchedFilm]


class RecommendResponse(BaseModel):
    title: str
    year: int
    overview: str
    poster_url: str
    imdb_rating: str
    metascore: str
    rotten_tomatoes: str
    explanation: str


# Request classification via local Ollama (qwen2.5:7b)
async def _classify_request(client: httpx.AsyncClient, user_request: str) -> dict:
    fallback = {
        "type": "B",
        "search_title": None,
        "genres": [],
        "decade": None,
        "keywords": [user_request],
    }
    prompt = (
        "Classify this movie request and extract parameters. Respond in JSON only, no explanation.\n\n"
        f"Request: {user_request}\n\n"
        "Respond with exactly this shape:\n"
        '{"type": "A" or "B", "search_title": string or null, "genres": [string], '
        '"decade": string or null, "keywords": [string]}\n\n'
        "Type A = user names a specific title or says 'like X' (extract X as search_title).\n"
        "Type B = user describes what they want without naming a title.\n"
        'genres: list any mentioned genres e.g. ["sci-fi", "comedy"]\n'
        'decade: extract if mentioned e.g. "2000s", null if not\n'
        'keywords: any specific themes or descriptors e.g. ["space", "time travel"]'
    )
    try:
        resp = await client.post(
            OLLAMA_URL,
            json={"model": "qwen2.5:7b", "stream": False, "format": "json", "prompt": prompt},
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "")
        return json.loads(raw)
    except Exception:
        return fallback


def _decade_to_date_range(decade: str | None) -> tuple[str | None, str | None]:
    if not decade:
        return None, None
    m = DECADE_RE.search(decade)
    if not m:
        return None, None
    token = m.group(1).lower().replace("s", "")
    # token is like "2000", "90", "80"
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


async def _qwen_suggest_titles(client: httpx.AsyncClient, user_request: str) -> list[dict]:
    prompt = (
        f"Suggest 8 real movies matching: {user_request}\n"
        "Respond in JSON only with this exact shape:\n"
        '{"titles": [{"title": string, "year": int}]}'
    )
    try:
        resp = await client.post(
            OLLAMA_URL,
            json={"model": "qwen2.5:7b", "stream": False, "format": "json", "prompt": prompt},
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "")
        return json.loads(raw).get("titles", [])
    except Exception:
        return []


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


async def _omdb_enrich(client: httpx.AsyncClient, imdb_id: str, api_key: str) -> dict:
    resp = await client.get(
        OMDB_URL,
        params={"i": imdb_id, "apikey": api_key},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    rt = next(
        (r["Value"] for r in data.get("Ratings", []) if r.get("Source") == "Rotten Tomatoes"),
        "N/A",
    )
    return {
        "imdb_rating": data.get("imdbRating", "N/A"),
        "metascore": data.get("Metascore", "N/A"),
        "rotten_tomatoes": rt,
    }


@app.post("/recommend", response_model=RecommendResponse)
async def recommend(body: RecommendRequest):
    tmdb_token = os.getenv("TMDB_API_KEY")
    omdb_key = os.getenv("OMDB_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if not tmdb_token:
        raise HTTPException(status_code=500, detail="TMDB_API_KEY not configured")
    if not omdb_key:
        raise HTTPException(status_code=500, detail="OMDB_API_KEY not configured")
    if not anthropic_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    # Build set for O(1) watched lookups: (lower-title, year)
    watched_set: set[tuple[str, int | None]] = {
        (f.title.lower(), f.year) for f in body.watched
    }

    async with httpx.AsyncClient() as client:
        # --- Step 1: Classify request via Ollama ---
        classification = await _classify_request(client, body.request)
        req_type = classification.get("type", "B")

        # --- Step 2: TMDB search based on type ---
        raw_candidates: list[dict] = []
        if req_type == "A":
            search_title = classification.get("search_title") or body.request
            try:
                raw_candidates = await _tmdb_search(client, search_title, tmdb_token)
            except httpx.HTTPError:
                pass
        else:
            genres = classification.get("genres") or []
            genre_ids = [GENRE_MAP[g.lower()] for g in genres if g.lower() in GENRE_MAP]
            keyword_ids = await _resolve_keywords(
                client, classification.get("keywords") or [], tmdb_token
            )

            if genre_ids or keyword_ids:
                try:
                    raw_candidates = await _tmdb_discover(
                        client,
                        genre_ids=genre_ids,
                        keyword_ids=keyword_ids,
                        decade=classification.get("decade"),
                        token=tmdb_token,
                    )
                except httpx.HTTPError:
                    pass
            else:
                # No filters resolved — ask Qwen to suggest titles directly
                suggested = await _qwen_suggest_titles(client, body.request)
                seen_ids: set[int] = set()
                for i, entry in enumerate(suggested):
                    title = entry.get("title")
                    if not title:
                        continue
                    if i > 0:
                        await asyncio.sleep(TMDB_DELAY)
                    try:
                        results = await _tmdb_search(client, title, tmdb_token)
                    except httpx.HTTPError:
                        continue
                    if results and results[0]["id"] not in seen_ids:
                        seen_ids.add(results[0]["id"])
                        raw_candidates.append(results[0])

        # --- Step 3: Fetch external IDs for each candidate ---
        candidates: list[dict] = []
        for i, r in enumerate(raw_candidates):
            if i > 0:
                await asyncio.sleep(TMDB_DELAY)
            try:
                ext = await _tmdb_external_ids(client, r["id"], tmdb_token)
            except httpx.HTTPError:
                ext = {}
            candidates.append({**r, "imdb_id": ext.get("imdb_id")})

        # --- Step 4: OMDb enrichment ---
        enriched: list[dict] = []
        for c in candidates:
            omdb: dict = {"imdb_rating": "N/A", "metascore": "N/A", "rotten_tomatoes": "N/A"}
            if c.get("imdb_id"):
                try:
                    omdb = await _omdb_enrich(client, c["imdb_id"], omdb_key)
                except httpx.HTTPError:
                    pass
            enriched.append({**c, **omdb})

        # --- Step 5: Filter watched ---
        def _is_watched(c: dict) -> bool:
            title = c.get("title", "").lower()
            year_str = (c.get("release_date") or "")[:4]
            year = int(year_str) if year_str.isdigit() else None
            return (title, year) in watched_set

        unwatched = [c for c in enriched if not _is_watched(c)]
        if not unwatched:
            raise HTTPException(status_code=404, detail="No unwatched candidates found")

        # --- Step 6: Claude picks the best match ---
        candidate_summary = [
            {
                "tmdb_id": c["id"],
                "title": c.get("title"),
                "year": (c.get("release_date") or "")[:4],
                "overview": c.get("overview"),
                "imdb_rating": c.get("imdb_rating"),
                "metascore": c.get("metascore"),
                "rotten_tomatoes": c.get("rotten_tomatoes"),
            }
            for c in unwatched
        ]

        ai_client = anthropic.Anthropic(api_key=anthropic_key)
        message = ai_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=(
                "You are a movie recommendation expert. Given a user request and a list "
                "of candidate movies with ratings, pick the single best match. Consider "
                "how well it matches the request, critical reception, and overall quality. "
                "Respond in JSON only with this exact shape:\n"
                '{"tmdb_id": int, "title": string, "year": int, "explanation": string}'
            ),
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(
                        {"request": body.request, "candidates": candidate_summary},
                        ensure_ascii=False,
                    ),
                }
            ],
        )

        raw = message.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
        try:
            pick = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=500, detail=f"Claude returned malformed JSON: {exc}"
            ) from exc

        chosen_id = pick.get("tmdb_id")
        if not chosen_id:
            raise HTTPException(status_code=500, detail="Claude response missing tmdb_id")

        # --- Step 7: Fetch full movie details and build response ---
        details_resp = await client.get(
            TMDB_DETAILS_URL.format(tmdb_id=chosen_id),
            headers={"Authorization": f"Bearer {tmdb_token}"},
            timeout=15,
        )
        details_resp.raise_for_status()
        details = details_resp.json()

        ratings = next((c for c in enriched if c.get("id") == chosen_id), {})
        poster_path = details.get("poster_path") or ""
        return RecommendResponse(
            title=details.get("title", pick.get("title", "")),
            year=int((details.get("release_date") or "0")[:4]),
            overview=details.get("overview", ""),
            poster_url=f"{POSTER_BASE}{poster_path}" if poster_path else "",
            imdb_rating=ratings.get("imdb_rating", "N/A"),
            metascore=ratings.get("metascore", "N/A"),
            rotten_tomatoes=ratings.get("rotten_tomatoes", "N/A"),
            explanation=pick.get("explanation", ""),
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
