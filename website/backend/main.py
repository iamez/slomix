import sys
import os
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)

from website.backend.routers import api, auth, predictions
from website.backend.dependencies import init_db_pool, close_db_pool

# Load environment variables - check website folder first, then project root
website_env = os.path.join(os.path.dirname(__file__), "../.env")
if os.path.exists(website_env):
    load_dotenv(website_env)
else:
    load_dotenv(os.path.join(project_root, ".env"))

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment
WEBSITE_PORT = int(os.getenv("WEBSITE_PORT", "8000"))
WEBSITE_HOST = os.getenv("WEBSITE_HOST", "0.0.0.0")
SESSION_SECRET = os.getenv("SESSION_SECRET", "super-secret-key-change-me")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")

# Warn if using default secret in production
if SESSION_SECRET == "super-secret-key-change-me":
    logger.warning("⚠️  Using default SESSION_SECRET - change this in production!")

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
    allow_headers=["*"],
)

# Session Middleware
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

# Include Routers
app.include_router(api.router, prefix="/api", tags=["API"])
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["Predictions"])

# Serve Static Files (Frontend)
# Mount this LAST to avoid conflicts with API routes
static_dir = os.path.join(project_root, "website")
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Slomix Website Backend Starting...")
    await init_db_pool()  # Initialize shared DB pool once
    logger.info("✅ Slomix Website Backend Ready")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 Slomix Website Backend Stopping...")
    await close_db_pool()  # Clean up DB pool
    logger.info("✅ Slomix Website Backend Stopped")


# Trigger reload
