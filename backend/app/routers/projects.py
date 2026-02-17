from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.models import get_db, Project

router = APIRouter()


@router.get("/")
async def list_projects(db: Session = Depends(get_db)):
    """List all projects."""
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    return {
        "projects": [p.to_dict() for p in projects]
    }


@router.get("/{project_id}")
async def get_project(project_id: UUID, db: Session = Depends(get_db)):
    """Get a specific project by ID."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.to_dict()


@router.get("/{project_id}/assets")
@router.get("/{project_id}/assets/")
async def get_project_assets(project_id: UUID, db: Session = Depends(get_db)):
    """Get all assets for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    assets = [
        {
            "id": str(a.id),
            "asset_type": a.asset_type,
            "title": a.title,
            "description": a.description,
            "file_url": a.file_url,
            "duration_seconds": a.duration_seconds,
            "status": a.status
        }
        for a in project.assets
    ]
    
    return {"assets": assets}


@router.post("/{project_id}/download-all")
async def download_all_assets(project_id: UUID, db: Session = Depends(get_db)):
    """Generate ZIP file with all assets for download."""
    # TODO: Implement ZIP generation
    return {"message": "ZIP generation not yet implemented"}
