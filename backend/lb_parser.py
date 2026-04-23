import pandas as pd
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
    watched: list[FilmEntry]         # for exclusion purposes
    rated: list[FilmEntry]           # for taste data
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
