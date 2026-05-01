from pydantic import BaseModel


class WatchedFilm(BaseModel):
    title: str
    year: int | None = None


class RatedFilm(BaseModel):
    title: str
    year: int | None = None
    rating: float | None = None


class RecommendRequest(BaseModel):
    request: str
    watched: list[WatchedFilm]
    rated: list[RatedFilm] = []


class RecommendResponse(BaseModel):
    title: str
    year: int
    overview: str
    poster_url: str
    imdb_score: str
    metascore: str
    rotten_tomatoes: str
    explanation: str
