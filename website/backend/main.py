import sys
import os
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(project_root)

from website.backend.routers import api, auth, predictions
from website.backend.dependencies import init_db_pool, close_db_pool

# Load environment variables
load_dotenv(os.path.join(project_root, ".env"))

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Slomix Website Backend")

# Session Middleware
SECRET_KEY = os.getenv("SESSION_SECRET", "super-secret-key-change-me")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

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
