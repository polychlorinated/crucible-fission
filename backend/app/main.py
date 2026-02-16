from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import os
import uuid
from datetime import datetime

from app.config import get_settings
from app.models import get_db, create_tables, Project, Transcript, Moment, Asset
from app.services.transcription import transcribe_video
from app.services.analysis import analyze_transcript
from app.services.video import extract_clip, create_vertical_version, add_captions
from app.services.storage import upload_to_drive

settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="Crucible Fission Reactor",
    description="Transform one video into 50+ content assets",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure temp directory exists
os.makedirs(settings.temp_dir, exist_ok=True)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    import time
    max_retries = 5
    for attempt in range(max_retries):
        try:
            create_tables()
            print("Database initialized")
            return
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Database connection failed (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(2)
            else:
                print(f"Database connection failed after {max_retries} attempts: {e}")
                raise


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "Crucible Fission Reactor",
        "version": "0.1.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "database": "connected",
        "whisper_model": settings.whisper_model
    }


# Import and include routers
from app.routers import projects, upload, processing

app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(upload.router, prefix="/api/upload", tags=["upload"])
app.include_router(processing.router, prefix="/api/processing", tags=["processing"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
