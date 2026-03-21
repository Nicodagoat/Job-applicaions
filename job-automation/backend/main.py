"""
Job Application Platform — FastAPI backend entry point.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Load environment variables from .env
load_dotenv(Path(__file__).parent.parent / "config" / ".env")

# Load settings
_SETTINGS_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"
with open(_SETTINGS_PATH) as _f:
    _SETTINGS = yaml.safe_load(_f)

# Configure logging
logging.basicConfig(
    level=getattr(logging, _SETTINGS["app"]["log_level"]),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent.parent / "logs" / "app.log"),
    ],
)
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Startup / shutdown                                                           #
# --------------------------------------------------------------------------- #

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Job Application Platform...")
    # Initialise database
    from database.db import init_db
    init_db()
    # Ensure log and document directories exist
    (Path(__file__).parent.parent / "logs" / "screenshots").mkdir(parents=True, exist_ok=True)
    (Path(__file__).parent.parent / "documents").mkdir(parents=True, exist_ok=True)
    logger.info("Platform ready.")
    yield
    # Shutdown
    logger.info("Shutting down platform.")


# --------------------------------------------------------------------------- #
# App                                                                          #
# --------------------------------------------------------------------------- #

app = FastAPI(
    title=_SETTINGS["app"]["name"],
    version=_SETTINGS["app"]["version"],
    description="Automated job application platform for ESG/sustainability roles.",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=_SETTINGS["backend"]["cors_origins"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
from backend.api.jobs import router as jobs_router
from backend.api.documents import router as documents_router
from backend.api.scraper import router as scraper_router
from backend.api.settings import router as settings_router
from backend.api.profile import router as profile_router

app.include_router(jobs_router)
app.include_router(documents_router)
app.include_router(scraper_router)
app.include_router(settings_router)
app.include_router(profile_router)


# --------------------------------------------------------------------------- #
# Root                                                                         #
# --------------------------------------------------------------------------- #

@app.get("/")
def root():
    return {
        "name": _SETTINGS["app"]["name"],
        "version": _SETTINGS["app"]["version"],
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


# --------------------------------------------------------------------------- #
# Run directly                                                                 #
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=_SETTINGS["backend"]["host"],
        port=_SETTINGS["backend"]["port"],
        reload=_SETTINGS["app"]["debug"],
    )
