# parser.py
import pandas as pd
import sys
from pathlib import Path
from datetime import date
from pydantic import BaseModel
from typing import Optional


# --- Models ---

class FilmEntry(BaseModel):
    title: str
    year: Optional[int] = None
    rating: Optional[float] = None
    watched_date: Optional[date] = None
    letterboxd_uri: Optional[str] = None

class UserProfile(BaseModel):
    watched: list[FilmEntry]         # all watched films (for exclusion)
    rated: list[FilmEntry]           # rated films only (for taste)
    total_watched: int
    total_rated: int
    has_taste_data: bool
    parse_errors: list[str]


# --- Internal parsers ---

def _parse_watched(path: Path) -> tuple[list[FilmEntry], list[str]]:
    """Parse watched.csv - Date, Name, Year, Letterboxd URI"""
    films, errors = [], []
    try:
        df = pd.read_csv(path)
    except Exception as e:
        return [], [f"Could not read {path.name}: {e}"]

    for idx, row in df.iterrows():
        try:
            year = int(row["Year"]) if pd.notna(row.get("Year")) else None
            watched_date = pd.to_datetime(row["Date"]).date() if pd.notna(row.get("Date")) else None
            films.append(FilmEntry(
                title=str(row["Name"]).strip(),
                year=year,
                watched_date=watched_date,
                letterboxd_uri=row.get("Letterboxd URI") or None,
            ))
        except Exception as e:
            errors.append(f"watched.csv row {idx} ({row.get('Name', '?')}): {e}")

    return films, errors


def _parse_ratings(path: Path) -> tuple[list[FilmEntry], list[str]]:
    """Parse ratings.csv — Date, Name, Year, Letterboxd URI, Rating"""
    films, errors = [], []
    try:
        df = pd.read_csv(path)
    except Exception as e:
        return [], [f"Could not read {path.name}: {e}"]

    for idx, row in df.iterrows():
        try:
            year = int(row["Year"]) if pd.notna(row.get("Year")) else None
            rating = float(row["Rating"]) if pd.notna(row.get("Rating")) else None
            watched_date = pd.to_datetime(row["Date"]).date() if pd.notna(row.get("Date")) else None
            films.append(FilmEntry(
                title=str(row["Name"]).strip(),
                year=year,
                rating=rating,
                watched_date=watched_date,
                letterboxd_uri=row.get("Letterboxd URI") or None,
            ))
        except Exception as e:
            errors.append(f"ratings.csv row {idx} ({row.get('Name', '?')}): {e}")

    return films, errors


# --- Entry Point ---

def build_user_profile(
    watched_path: Path,
    ratings_path: Optional[Path] = None,
) -> UserProfile:
    all_errors = []

    watched, w_errors = _parse_watched(watched_path)
    all_errors.extend(w_errors)

    rated, r_errors = [], []
    if ratings_path and ratings_path.exists():
        rated, r_errors = _parse_ratings(ratings_path)
        all_errors.extend(r_errors)

    return UserProfile(
        watched=watched,
        rated=rated,
        total_watched=len(watched),
        total_rated=len(rated),
        has_taste_data=len(rated) > 0,
        parse_errors=all_errors,
    )


# CLI Test
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run parser.py watched.csv [ratings.csv]")
        sys.exit(1)

    watched_path = Path(sys.argv[1])
    ratings_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    profile = build_user_profile(watched_path, ratings_path)

    print(f"\nWatched: {profile.total_watched} films")
    print(f"Rated:   {profile.total_rated} films")
    print(f"Taste data available: {profile.has_taste_data}")

    if profile.parse_errors:
        print(f"\nWarnings ({len(profile.parse_errors)}):")
        for e in profile.parse_errors:
            print(f"  - {e}")

    print("\nFirst 5 watched:")
    for f in profile.watched[:5]:
        print(f"  {f.title} ({f.year})")

    if profile.rated:
        print("\nFirst 5 rated:")
        for f in profile.rated[:5]:
            print(f"  {f.title} ({f.year})  ★ {f.rating}")

    out_path = watched_path.stem + "_profile.json"
    with open(out_path, "w") as f:
        f.write(profile.model_dump_json(indent=2))
    print(f"\nFull output saved to {out_path}")