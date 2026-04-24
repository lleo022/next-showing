import httpx

OMDB_URL = "http://www.omdbapi.com/"


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
        "imdb_score": data.get("imdbRating", "N/A"),
        "metascore": data.get("Metascore", "N/A"),
        "rotten_tomatoes": rt,
    }
