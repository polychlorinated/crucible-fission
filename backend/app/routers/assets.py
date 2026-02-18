"""Assets router for downloading generated content."""

import os
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.models import get_db, Asset, Project

router = APIRouter()


@router.get("/project/{project_id}")
async def list_project_assets(project_id: UUID, db: Session = Depends(get_db)):
    """List all assets for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    assets = db.query(Asset).filter(Asset.project_id == project_id).all()
    
    return {
        "project_id": str(project_id),
        "assets": [
            {
                "id": str(a.id),
                "asset_type": a.asset_type,
                "title": a.title,
                "description": a.description,
                "content": a.content,
                "file_url": a.file_url,
                "file_size_mb": float(a.file_size_mb) if a.file_size_mb else None,
                "duration_seconds": a.duration_seconds,
                "dimensions": a.dimensions,
                "format": a.format,
                "status": a.status,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "moment_id": str(a.moment_id) if a.moment_id else None,
            }
            for a in assets
        ]
    }


@router.get("/{asset_id}")
async def get_asset(asset_id: UUID, db: Session = Depends(get_db)):
    """Get asset details."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    return {
        "id": str(asset.id),
        "project_id": str(asset.project_id),
        "moment_id": str(asset.moment_id) if asset.moment_id else None,
        "asset_type": asset.asset_type,
        "title": asset.title,
        "description": asset.description,
        "content": asset.content,
        "file_url": asset.file_url,
        "file_size_mb": float(asset.file_size_mb) if asset.file_size_mb else None,
        "duration_seconds": asset.duration_seconds,
        "dimensions": asset.dimensions,
        "format": asset.format,
        "status": asset.status,
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
    }


@router.get("/{asset_id}/download")
async def download_asset(asset_id: UUID, db: Session = Depends(get_db)):
    """Download asset file."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    # Check if file exists locally
    if asset.file_path and os.path.exists(asset.file_path):
        filename = os.path.basename(asset.file_path)
        media_type = _get_media_type(asset.format)
        
        return FileResponse(
            path=asset.file_path,
            filename=filename,
            media_type=media_type
        )
    
    # If external URL exists, redirect to it
    if asset.file_url:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=asset.file_url)
    
    raise HTTPException(status_code=404, detail="Asset file not available")


@router.get("/{asset_id}/content")
async def get_asset_content(asset_id: UUID, db: Session = Depends(get_db)):
    """Get text content for text-based assets (quotes, emails, social posts, etc)."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    text_types = ["quote_card", "email", "social_post", "blog_outline", "captions"]
    
    if asset.asset_type in text_types:
        return {
            "id": str(asset.id),
            "asset_type": asset.asset_type,
            "title": asset.title,
            "content": asset.content,
        }
    
    # For video/audio, return metadata only
    return {
        "id": str(asset.id),
        "asset_type": asset.asset_type,
        "title": asset.title,
        "content": asset.content,  # May contain transcript or description
    }


def _get_media_type(format: str) -> str:
    """Get MIME type for file format."""
    mime_types = {
        "mp4": "video/mp4",
        "mov": "video/quicktime",
        "webm": "video/webm",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "txt": "text/plain",
        "json": "application/json",
    }
    return mime_types.get(format.lower(), "application/octet-stream")
