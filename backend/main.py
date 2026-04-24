import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import parse, recommend

_REQUIRED_KEYS = ("TMDB_API_KEY", "OMDB_API_KEY", "ANTHROPIC_API_KEY")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    missing = [k for k in _REQUIRED_KEYS if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parse.router)
app.include_router(recommend.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
