import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from lb_parser import UserProfile, build_user_profile

router = APIRouter()


@router.post("/parse", response_model=UserProfile)
async def parse(
    watched_file: UploadFile = File(...),
    ratings_file: UploadFile | None = File(None),
):
    watched_tmp = None
    ratings_tmp = None

    try:
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
