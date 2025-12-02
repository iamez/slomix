from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from website.backend.dependencies import get_db
from website.backend.local_database_adapter import DatabaseAdapter
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class ClipSubmission(BaseModel):
    title: str
    url: str
    description: str = ""

class ConfigSubmission(BaseModel):
    title: str
    description: str
    content: str

@router.get("/clips")
async def get_clips(db: DatabaseAdapter = Depends(get_db)):
    """Get all clips"""
    return await db.fetch_all("SELECT * FROM clips ORDER BY date DESC")

@router.post("/clips")
async def submit_clip(request: Request, payload: ClipSubmission, db: DatabaseAdapter = Depends(get_db)):
    """Submit a new clip"""
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Must be logged in to submit clips")
        
    author = user.get("username", "Anonymous")
    
    await db.execute(
        "INSERT INTO clips (title, author, url, description) VALUES (?, ?, ?, ?)",
        (payload.title, author, payload.url, payload.description)
    )
    
    return {"status": "success", "message": "Clip submitted"}

@router.get("/configs")
async def get_configs(db: DatabaseAdapter = Depends(get_db)):
    """Get all configs"""
    return await db.fetch_all("SELECT * FROM configs ORDER BY date DESC")

@router.post("/configs")
async def submit_config(request: Request, payload: ConfigSubmission, db: DatabaseAdapter = Depends(get_db)):
    """Submit a new config"""
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Must be logged in to submit configs")
        
    author = user.get("username", "Anonymous")
    
    await db.execute(
        "INSERT INTO configs (title, author, description, content) VALUES (?, ?, ?, ?)",
        (payload.title, author, payload.description, payload.content)
    )
    
    return {"status": "success", "message": "Config submitted"}
