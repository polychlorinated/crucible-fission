from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime

from app.models import get_db, Project

router = APIRouter()


@router.get("/status/{project_id}")
async def get_status(project_id: UUID, db: Session = Depends(get_db)):
    """Get processing status for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return {
        "project_id": str(project.id),
        "status": project.status,
        "processing_stage": project.processing_stage,
        "progress_percent": project.progress_percent,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None
    }


@router.post("/{project_id}/retry")
async def retry_processing(project_id: UUID, db: Session = Depends(get_db)):
    """Retry failed processing."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project.status != "failed":
        raise HTTPException(status_code=400, detail="Can only retry failed projects")
    
    # Reset status
    project.status = "pending"
    project.processing_stage = "retry_queued"
    project.progress_percent = 0
    db.commit()
    
    # TODO: Add to background processing queue
    
    return {"message": "Project queued for retry", "project_id": str(project_id)}


@router.get("/{project_id}/transcript")
async def get_transcript(project_id: UUID, db: Session = Depends(get_db)):
    """Get transcript for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not project.transcript:
        raise HTTPException(status_code=404, detail="Transcript not yet available")
    
    return {
        "project_id": str(project.id),
        "full_text": project.transcript.full_text,
        "language": project.transcript.language,
        "segments": project.transcript.segments
    }


@router.get("/{project_id}/moments")
async def get_moments(project_id: UUID, db: Session = Depends(get_db)):
    """Get identified moments for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    moments = [
        {
            "id": str(m.id),
            "moment_type": m.moment_type,
            "start_time": float(m.start_time),
            "end_time": float(m.end_time),
            "transcript": m.transcript,
            "summary": m.summary,
            "sentiment_score": float(m.sentiment_score) if m.sentiment_score else None,
            "importance_score": float(m.importance_score) if m.importance_score else None,
            "quotable_text": m.quotable_text,
            "quotable_score": float(m.quotable_score) if m.quotable_score else None
        }
        for m in project.moments
    ]
    
    return {"moments": moments}
