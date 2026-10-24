"""FastAPI application entry point.

Run with:  uvicorn app.main:app --reload --port 8000   (from the backend/ folder)
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes.agent import router as agent_router
from .config import get_settings
from .services.run_manager import get_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("newsletter_agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    for warning in settings.validate_startup():
        logger.warning("CONFIG: %s", warning)
    logger.info("LLM provider: %s | research sources: %s", settings.llm_provider, ", ".join(settings.search_sources))
    get_manager()  # open the SQLite checkpointer and recover run records
    yield


app = FastAPI(title="Newsletter Agent API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().frontend_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/config")
def public_config():
    """Non-secret configuration for the UI (no API keys are ever returned)."""
    s = get_settings()
    return {
        "default_provider": s.llm_provider,
        "providers": s.provider_status(),
        "research_sources": s.search_sources,
        "max_articles": s.max_articles,
        "max_revisions": s.max_revisions,
        "default_lookback_days": s.default_lookback_days,
        "critic_provider": s.critic_provider or None,
        "fallback_provider": s.llm_fallback_provider or None,
        "warnings": s.validate_startup(),
    }
