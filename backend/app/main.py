"""
Sanjeevani — Production Health Information System
FastAPI application entry point.
"""
from contextlib import asynccontextmanager

import sentry_sdk
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api import health, webhook, admin, ingest
from app.core.config import settings
from app.core.logging import configure_logging
from app.services.embedder import EmbedderService
from app.services.vector_store import VectorStoreService
from app.services.session_store import SessionStore

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    configure_logging()
    log.info("sanjeevani.starting", env=settings.APP_ENV)

    # Sentry
    if settings.SENTRY_DSN:
        sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.1)

    # Warm up services
    app.state.embedder = EmbedderService()
    app.state.vector_store = VectorStoreService()
    app.state.session_store = SessionStore()
    await app.state.vector_store.ensure_collection()

    log.info("sanjeevani.ready")
    yield

    log.info("sanjeevani.shutting_down")


app = FastAPI(
    title="Sanjeevani",
    description="Production health information system via WhatsApp & SMS",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.APP_ENV != "production" else None,
    redoc_url=None,
)

# ── Middleware ─────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.APP_ENV == "production":
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

# ── Prometheus ─────────────────────────────────────────────────────────────────
if settings.PROMETHEUS_ENABLED:
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router, tags=["health"])
app.include_router(webhook.router, prefix="/webhook", tags=["webhook"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
