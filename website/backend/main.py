import sys
import os
import asyncio
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

try:
    from prometheus_fastapi_instrumentator import Instrumentator
except ImportError:  # pragma: no cover - optional dependency fallback
    Instrumentator = None

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)

# Load environment variables BEFORE importing logging (for LOG_LEVEL env var)
website_env = os.path.join(os.path.dirname(__file__), "../.env")
if os.path.exists(website_env):
    load_dotenv(website_env)
else:
    load_dotenv(os.path.join(project_root, ".env"))

# Setup logging (must happen before other imports that use logging)
from website.backend.logging_config import setup_logging, get_app_logger
from website.backend.middleware import (
    RequestLoggingMiddleware,
    HTTPCacheMiddleware,
    RateLimitMiddleware,
)
from website.backend.env_utils import getenv_int

# Configure logging from environment
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT_JSON = os.getenv("LOG_FORMAT_JSON", "false").lower() == "true"

setup_logging(
    log_level=LOG_LEVEL,
    json_logs=LOG_FORMAT_JSON,
    console_output=True,
)

logger = get_app_logger(__name__)

from website.backend.routers import api, auth, predictions, greatshot, greatshot_topshots, uploads, availability, planning
from website.backend.dependencies import init_db_pool, close_db_pool, get_db_pool
from website.backend.services.greatshot_store import get_greatshot_storage
from website.backend.services.greatshot_jobs import (
    GreatshotJobService,
    get_greatshot_job_service,
    set_greatshot_job_service,
)
from website.backend.services.http_cache_backend import create_cache_backend_from_env
from greatshot.config import CONFIG as GREATSHOT_CONFIG

# Configuration from environment
WEBSITE_PORT = getenv_int("WEBSITE_PORT", 7000)
WEBSITE_HOST = os.getenv("WEBSITE_HOST", "0.0.0.0")
SESSION_SECRET = os.getenv("SESSION_SECRET")
SESSION_HTTPS_ONLY = os.getenv("SESSION_HTTPS_ONLY", "false").lower() == "true"
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS", "http://localhost:7000,http://127.0.0.1:7000"
).split(",")
PROMETHEUS_ENABLED = os.getenv("PROMETHEUS_ENABLED", "true").lower() == "true"

cache_backend = create_cache_backend_from_env()


def _normalize_origin(origin: str | None) -> str | None:
    if not origin:
        return None
    parsed = urlsplit(origin.strip())
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def _parse_origin_list(raw_value: str) -> list[str]:
    return [value.strip() for value in raw_value.split(",") if value.strip()]


def _csrf_allowed_origins() -> set[str]:
    configured = _parse_origin_list(os.getenv("CSRF_ALLOWED_ORIGINS", ""))
    if not configured:
        configured = [*CORS_ORIGINS]
        frontend_origin = os.getenv("FRONTEND_ORIGIN")
        public_origin = os.getenv("PUBLIC_FRONTEND_ORIGIN")
        if frontend_origin:
            configured.append(frontend_origin)
        if public_origin:
            configured.append(public_origin)
    return {
        normalized
        for normalized in (_normalize_origin(origin) for origin in configured)
        if normalized
    }


class CSRFMiddleware(BaseHTTPMiddleware):
    """Origin-check guard for session-authenticated mutating requests."""

    _MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def __init__(
        self,
        app,
        *,
        enabled: bool,
        allowed_origins: set[str],
    ):
        super().__init__(app)
        self.enabled = enabled
        self.allowed_origins = allowed_origins

    async def dispatch(self, request: Request, call_next):
        if not self.enabled or request.method.upper() not in self._MUTATING_METHODS:
            return await call_next(request)
        if not (request.url.path.startswith("/api/") or request.url.path.startswith("/auth/")):
            return await call_next(request)
        if not request.session.get("user"):
            return await call_next(request)

        allowed_origins = self.allowed_origins
        if not allowed_origins:
            inferred_origin = _normalize_origin(str(request.base_url))
            if inferred_origin:
                allowed_origins = {inferred_origin}

        request_origin = _normalize_origin(request.headers.get("origin"))
        if not request_origin:
            request_origin = _normalize_origin(request.headers.get("referer"))
        if request_origin and request_origin in allowed_origins:
            return await call_next(request)

        return JSONResponse(status_code=403, content={"detail": "CSRF origin check failed"})


CSRF_ORIGIN_CHECK_ENABLED = os.getenv("CSRF_ORIGIN_CHECK_ENABLED", "true").lower() == "true"
CSRF_ALLOWED_ORIGINS = _csrf_allowed_origins()

# Validate SESSION_SECRET is properly configured
if not SESSION_SECRET or SESSION_SECRET == "super-secret-key-change-me":
    raise ValueError(
        "SESSION_SECRET environment variable must be set to a secure random value. "
        "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
    )

app = FastAPI(
    title="Slomix Website Backend",
    description="ET:Legacy Stats Website API",
    version="1.0.0",
)

# CORS Middleware - must be added before other middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Accept",
        "Origin",
    ],
)

# CSRF middleware (added before session middleware so session runs first in the stack)
app.add_middleware(
    CSRFMiddleware,
    enabled=CSRF_ORIGIN_CHECK_ENABLED,
    allowed_origins=CSRF_ALLOWED_ORIGINS,
)

# Session Middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    https_only=SESSION_HTTPS_ONLY,
    same_site="lax",
    max_age=86400,  # 24 hours
)

# Rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# HTTP cache middleware (ETag + Cache-Control + Redis/memory cache)
app.add_middleware(HTTPCacheMiddleware, cache_backend=cache_backend)

# Request Logging Middleware (added after session so it can access session data)
app.add_middleware(RequestLoggingMiddleware)

# Include Routers
app.include_router(api.router, prefix="/api", tags=["API"])
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["Predictions"])
app.include_router(greatshot.router, prefix="/api", tags=["Greatshot"])
app.include_router(greatshot_topshots.router, prefix="/api", tags=["Greatshot Topshots"])
app.include_router(uploads.router, prefix="/api/uploads", tags=["Uploads"])
app.include_router(availability.router, prefix="/api/availability", tags=["Availability"])
app.include_router(planning.router, prefix="/api/planning", tags=["Planning"])

if PROMETHEUS_ENABLED and Instrumentator is not None:
    instrumentator = Instrumentator(excluded_handlers=["/metrics"])
    instrumentator.instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


@app.get("/greatshot", include_in_schema=False)
@app.get("/greatshot/demos", include_in_schema=False)
@app.get("/greatshot/clips", include_in_schema=False)
@app.get("/greatshot/highlights", include_in_schema=False)
@app.get("/greatshot/renders", include_in_schema=False)
@app.get("/greatshot/demo/{demo_id}", include_in_schema=False)
async def greatshot_spa_entry(demo_id: str | None = None):
    index_path = os.path.join(project_root, "website", "index.html")
    return FileResponse(index_path)


@app.get("/share/{upload_id}", include_in_schema=False)
async def share_redirect(upload_id: str):
    """Redirect /share/{id} to the SPA upload detail view."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/#/uploads/{upload_id}", status_code=302)


@app.get("/health", include_in_schema=False)
async def health_check():
    """Basic health endpoint with DB connectivity check."""
    try:
        db = get_db_pool()
        if db is None:
            raise RuntimeError("database pool not initialized")
        await asyncio.wait_for(db.fetch_one("SELECT 1"), timeout=2.0)
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "database": "unavailable",
                "detail": str(exc),
            },
        )
    return {"status": "ok", "database": "ok"}


# Serve Static Files (Frontend)
# Mount this LAST to avoid conflicts with API routes
static_dir = os.path.join(project_root, "website")
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Slomix Website Backend Starting...")
    await init_db_pool()  # Initialize shared DB pool once
    await cache_backend.connect()
    greatshot_startup_enabled = os.getenv("GREATSHOT_STARTUP_ENABLED", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not greatshot_startup_enabled:
        app.state.greatshot_start_task = None
        logger.info("Greatshot job service startup disabled by GREATSHOT_STARTUP_ENABLED")
        logger.info("✅ Slomix Website Backend Ready")
        return
    greatshot_storage = get_greatshot_storage(Path(project_root))
    job_service = GreatshotJobService(get_db_pool(), greatshot_storage)
    set_greatshot_job_service(job_service)
    startup_timeout = max(
        1.0,
        float(os.getenv("GREATSHOT_STARTUP_TIMEOUT_SECONDS", "20")),
    )
    async def _start_greatshot_service() -> None:
        try:
            await asyncio.wait_for(
                job_service.start(
                    analysis_workers=GREATSHOT_CONFIG.analysis_queue_workers,
                    render_workers=GREATSHOT_CONFIG.render_queue_workers,
                ),
                timeout=startup_timeout,
            )
        except Exception as exc:
            if "unable to open database file" in str(exc).lower():
                logger.info("Greatshot job service startup skipped: %s", exc)
            else:
                logger.warning("Greatshot job service startup skipped: %s", exc)

    app.state.greatshot_start_task = asyncio.create_task(
        _start_greatshot_service(),
        name="greatshot-startup",
    )
    logger.info("✅ Slomix Website Backend Ready")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 Slomix Website Backend Stopping...")
    start_task = getattr(app.state, "greatshot_start_task", None)
    if start_task is not None and not start_task.done():
        start_task.cancel()
        try:
            await asyncio.wait_for(start_task, timeout=2.0)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
    try:
        job_service = get_greatshot_job_service()
    except Exception:
        job_service = None
    if job_service is not None:
        await job_service.stop()
    await cache_backend.close()
    await close_db_pool()  # Clean up DB pool
    logger.info("✅ Slomix Website Backend Stopped")
