import os
import uuid
import shutil
from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from app.config import get_settings
from app.models import get_db, Project, create_tables
from app.services.video import get_video_duration

router = APIRouter()
settings = get_settings()


@router.post("/")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    content_type: str = Form("testimonial"),
    db: Session = Depends(get_db)
):
    """Upload a video file and start processing."""
    
    # Validate file type
    allowed_types = ["video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}"
        )
    
    # Create project
    project_id = uuid.uuid4()
    project = Project(
        id=project_id,
        input_filename=file.filename,
        content_type=content_type,
        status="uploading",
        progress_percent=5
    )
    db.add(project)
    db.commit()
    
    # Save uploaded file
    upload_dir = os.path.join(settings.temp_dir, str(project_id))
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, file.filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Get file size and duration
        file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
        duration = get_video_duration(file_path)
        
        project.file_size_mb = file_size
        project.duration_seconds = duration
        project.status = "pending"
        project.progress_percent = 10
        project.input_video_url = file_path
        
        db.commit()
        
        # Start processing in background
        background_tasks.add_task(process_video, str(project_id), file_path, db)
        
        return {
            "message": "Video uploaded successfully",
            "project_id": str(project_id),
            "status": "pending",
            "file_size_mb": round(file_size, 2),
            "duration_seconds": duration
        }
        
    except Exception as e:
        project.status = "failed"
        project.processing_stage = f"Upload error: {str(e)}"
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))


async def process_video(project_id: str, file_path: str, db: Session):
    """Background task to process the video."""
    from app.services.transcription import transcribe_video
    from app.services.analysis import analyze_transcript, generate_text_assets
    from app.services.video import extract_moment_clips
    
    try:
        # Get project
        project = db.query(Project).filter(Project.id == uuid.UUID(project_id)).first()
        if not project:
            return
        
        # Stage 1: Transcription
        project.status = "processing"
        project.processing_stage = "transcribing"
        project.progress_percent = 15
        db.commit()
        
        transcript_result = await transcribe_video(file_path, project_id, db)
        
        # Stage 2: Analysis
        project.processing_stage = "analyzing"
        project.progress_percent = 35
        db.commit()
        
        moments = await analyze_transcript(transcript_result, project_id, db)
        
        # Stage 3: Video clips
        project.processing_stage = "generating_video_clips"
        project.progress_percent = 60
        db.commit()
        
        await extract_moment_clips(moments, file_path, project_id, db)
        
        # Stage 4: Text assets
        project.processing_stage = "generating_text_assets"
        project.progress_percent = 85
        db.commit()
        
        await generate_text_assets(moments, transcript_result, project_id, db)
        
        # Complete
        project.status = "completed"
        project.processing_stage = "completed"
        project.progress_percent = 100
        db.commit()
        
    except Exception as e:
        project.status = "failed"
        project.processing_stage = f"Error: {str(e)}"
        db.commit()
        print(f"Processing error for {project_id}: {e}")
