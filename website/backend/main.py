import sys
import os
import asyncio
import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

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
from website.backend.middleware import RequestLoggingMiddleware

# Configure logging from environment
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT_JSON = os.getenv("LOG_FORMAT_JSON", "false").lower() == "true"

setup_logging(
    log_level=LOG_LEVEL,
    json_logs=LOG_FORMAT_JSON,
    console_output=True,
)

logger = get_app_logger(__name__)

from website.backend.routers import api, auth, predictions, greatshot, greatshot_topshots
from website.backend.dependencies import init_db_pool, close_db_pool, get_db_pool
from website.backend.services.greatshot_store import get_greatshot_storage
from website.backend.services.greatshot_jobs import (
    GreatshotJobService,
    get_greatshot_job_service,
    set_greatshot_job_service,
)
from greatshot.config import CONFIG as GREATSHOT_CONFIG

# Configuration from environment
WEBSITE_PORT = int(os.getenv("WEBSITE_PORT", "8000"))
WEBSITE_HOST = os.getenv("WEBSITE_HOST", "0.0.0.0")
SESSION_SECRET = os.getenv("SESSION_SECRET")
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
).split(",")

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
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Accept",
        "Origin",
    ],
)

# Session Middleware
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

# Request Logging Middleware (added after session so it can access session data)
app.add_middleware(RequestLoggingMiddleware)

# Include Routers
app.include_router(api.router, prefix="/api", tags=["API"])
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["Predictions"])
app.include_router(greatshot.router, prefix="/api", tags=["Greatshot"])
app.include_router(greatshot_topshots.router, prefix="/api", tags=["Greatshot Topshots"])


@app.get("/greatshot", include_in_schema=False)
@app.get("/greatshot/demos", include_in_schema=False)
@app.get("/greatshot/clips", include_in_schema=False)
@app.get("/greatshot/highlights", include_in_schema=False)
@app.get("/greatshot/renders", include_in_schema=False)
@app.get("/greatshot/demo/{demo_id}", include_in_schema=False)
async def greatshot_spa_entry(demo_id: str | None = None):
    index_path = os.path.join(project_root, "website", "index.html")
    return FileResponse(index_path)

# Serve Static Files (Frontend)
# Mount this LAST to avoid conflicts with API routes
static_dir = os.path.join(project_root, "website")
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Slomix Website Backend Starting...")
    await init_db_pool()  # Initialize shared DB pool once
    greatshot_storage = get_greatshot_storage(Path(project_root))
    job_service = GreatshotJobService(get_db_pool(), greatshot_storage)
    set_greatshot_job_service(job_service)
    await job_service.start(
        analysis_workers=GREATSHOT_CONFIG.analysis_queue_workers,
        render_workers=GREATSHOT_CONFIG.render_queue_workers,
    )
    logger.info("✅ Slomix Website Backend Ready")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 Slomix Website Backend Stopping...")
    try:
        await get_greatshot_job_service().stop()
    except Exception:
        logger.warning("Greatshot job service was not initialized during shutdown")
    await close_db_pool()  # Clean up DB pool
    logger.info("✅ Slomix Website Backend Stopped")
