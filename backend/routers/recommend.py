import asyncio
import json
import os
import re

import anthropic
import httpx
from fastapi import APIRouter, HTTPException

from models.schemas import RecommendRequest, RecommendResponse
from services.omdb import _omdb_enrich
from services.ollama import _classify_request, _qwen_suggest_titles
from services.tmdb import (
    GENRE_MAP,
    POSTER_BASE,
    TMDB_DELAY,
    _resolve_keywords,
    _tmdb_details,
    _tmdb_discover,
    _tmdb_external_ids,
    _tmdb_search,
)

router = APIRouter()


@router.post("/recommend", response_model=RecommendResponse)
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
            omdb: dict = {"imdb_score": "N/A", "metascore": "N/A", "rotten_tomatoes": "N/A"}
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
        details = await _tmdb_details(client, chosen_id, tmdb_token)

        ratings = next((c for c in enriched if c.get("id") == chosen_id), {})
        poster_path = details.get("poster_path") or ""
        return RecommendResponse(
            title=details.get("title", pick.get("title", "")),
            year=int((details.get("release_date") or "0")[:4]),
            overview=details.get("overview", ""),
            poster_url=f"{POSTER_BASE}{poster_path}" if poster_path else "",
            imdb_score=ratings.get("imdb_score", "N/A"),
            metascore=ratings.get("metascore", "N/A"),
            rotten_tomatoes=ratings.get("rotten_tomatoes", "N/A"),
            explanation=pick.get("explanation", ""),
        )
