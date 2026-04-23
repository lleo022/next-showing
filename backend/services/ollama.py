import json

import httpx

OLLAMA_URL = "http://localhost:11434/api/generate"


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
