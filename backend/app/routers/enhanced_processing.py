"""
Enhanced processing router with story arcs and visual generation.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any, List
import os

from app.models import get_db, Project, Transcript, Moment, Asset
from app.services.story_arcs import analyze_story_structure, StoryArcDetector
from app.services.visual_generator import VisualContentGenerator

router = APIRouter()


@router.post("/analyze-story/{project_id}")
async def analyze_project_story(
    project_id: str,
    db: Session = Depends(get_db)
):
    """
    Analyze project transcript for story structure and narrative arcs.
    """
    # Get project and transcript
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    transcript = db.query(Transcript).filter(Transcript.project_id == project_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")
    
    # Analyze story structure
    transcript_result = {
        'full_text': transcript.full_text,
        'segments': transcript.segments
    }
    
    story_analysis = analyze_story_structure(transcript_result)
    
    # Store story arcs in project metadata
    if not project.metadata:
        project.metadata = {}
    
    project.metadata['story_analysis'] = story_analysis
    db.commit()
    
    return {
        "project_id": project_id,
        "story_analysis": story_analysis
    }


@router.post("/generate-story-clips/{project_id}")
async def generate_story_based_clips(
    project_id: str,
    db: Session = Depends(get_db)
):
    """
    Generate video clips based on story arcs instead of isolated moments.
    Creates stitched narratives.
    """
    from app.services.video import extract_clip, stitch_clips
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get story analysis
    story_analysis = project.metadata.get('story_analysis', {}) if project.metadata else {}
    suggestions = story_analysis.get('clip_suggestions', [])
    
    if not suggestions:
        # Run analysis first
        transcript = db.query(Transcript).filter(Transcript.project_id == project_id).first()
        if transcript:
            transcript_result = {
                'full_text': transcript.full_text,
                'segments': transcript.segments
            }
            story_analysis = analyze_story_structure(transcript_result)
            suggestions = story_analysis.get('clip_suggestions', [])
    
    # Generate clips for each suggestion
    generated_clips = []
    
    for suggestion in suggestions[:3]:  # Top 3 story-based clips
        # Create asset for this story clip
        asset = Asset(
            project_id=project_id,
            asset_type="story_clip",
            title=f"Story: {suggestion['name']}",
            description=suggestion['description'],
            metadata={
                'segments': suggestion['segments'],
                'beats_used': suggestion['beats_used'],
                'purpose': suggestion['purpose']
            },
            status="processing"
        )
        db.add(asset)
        db.commit()
        
        # TODO: Implement clip stitching
        # For now, mark as ready for manual editing
        asset.status = "ready_for_edit"
        asset.content = f"Edit segments: {suggestion['segments']}"
        db.commit()
        
        generated_clips.append({
            'asset_id': str(asset.id),
            'name': suggestion['name'],
            'segments': suggestion['segments'],
            'purpose': suggestion['purpose'],
            'description': suggestion['description']
        })
    
    return {
        "project_id": project_id,
        "clips_generated": len(generated_clips),
        "clips": generated_clips
    }


@router.post("/generate-visuals/{project_id}")
async def generate_project_visuals(
    project_id: str,
    client_assets: List[str] = None,  # Optional: client's original image URLs
    db: Session = Depends(get_db)
):
    """
    Generate visual assets for project content.
    Priority: Client original > AI illustration > Stock
    """
    generator = VisualContentGenerator()
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get top moments for visual generation
    moments = db.query(Moment).filter(
        Moment.project_id == project_id
    ).order_by(Moment.quotable_score.desc()).all()
    
    generated_visuals = []
    
    # Generate visuals for top 3 moments
    for i, moment in enumerate(moments[:3]):
        if not moment.quotable_text:
            continue
        
        # Generate visuals for this quote
        visuals = await generator.generate_content_visuals(
            content=moment.quotable_text,
            content_type='quote_card',
            client_assets=client_assets
        )
        
        # Create asset for primary visual
        if visuals['primary_visual']:
            visual = visuals['primary_visual']
            
            asset = Asset(
                project_id=project_id,
                moment_id=moment.id,
                asset_type="visual_image",
                title=f"Visual for Quote {i+1}",
                description=f"{visual.asset_type}: {moment.quotable_text[:80]}...",
                file_url=visual.source_url,
                content=moment.quotable_text,
                metadata={
                    'sourcing': visuals['sourcing'],
                    'keywords': visuals['keywords'],
                    'ai_prompt': visuals.get('ai_prompt'),
                    'confidence': visual.confidence
                },
                status="completed"
            )
            db.add(asset)
            
            # Create alternative visual assets
            for j, alt in enumerate(visuals['alternatives'][:2]):
                alt_asset = Asset(
                    project_id=project_id,
                    moment_id=moment.id,
                    asset_type="visual_image_alt",
                    title=f"Visual Alternative {i+1}.{j+1}",
                    description=f"Alternative {alt.asset_type}",
                    file_url=alt.source_url,
                    metadata={
                        'sourcing': alt.asset_type,
                        'confidence': alt.confidence
                    },
                    status="completed"
                )
                db.add(alt_asset)
            
            db.commit()
            
            generated_visuals.append({
                'moment_id': str(moment.id),
                'quote': moment.quotable_text[:100],
                'primary_visual': {
                    'url': visual.source_url,
                    'type': visual.asset_type,
                    'sourcing': visuals['sourcing']
                },
                'alternatives': [
                    {'url': alt.source_url, 'type': alt.asset_type}
                    for alt in visuals['alternatives'][:2]
                ],
                'ai_prompt': visuals.get('ai_prompt')
            })
    
    return {
        "project_id": project_id,
        "visuals_generated": len(generated_visuals),
        "visuals": generated_visuals
    }


@router.post("/generate-quote-cards/{project_id}")
async def generate_quote_cards(
    project_id: str,
    brand_colors: Dict[str, str] = None,
    logo_url: str = None,
    client_assets: List[str] = None,
    db: Session = Depends(get_db)
):
    """
    Generate complete quote card specifications with visuals.
    Returns structured data for frontend to render.
    """
    generator = VisualContentGenerator()
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get best moment
    moment = db.query(Moment).filter(
        Moment.project_id == project_id
    ).order_by(Moment.quotable_score.desc()).first()
    
    if not moment or not moment.quotable_text:
        raise HTTPException(status_code=404, detail="No quotable content found")
    
    # Generate quote card specification
    quote_card = await generator.generate_quote_card_visuals(
        quote=moment.quotable_text,
        brand_colors=brand_colors,
        logo_url=logo_url,
        client_assets=client_assets
    )
    
    # Store as asset
    asset = Asset(
        project_id=project_id,
        moment_id=moment.id,
        asset_type="quote_card_spec",
        title="Quote Card Design",
        content=moment.quotable_text,
        metadata={
            'quote_card_spec': quote_card,
            'brand_colors': brand_colors,
            'logo_url': logo_url
        },
        status="completed"
    )
    db.add(asset)
    db.commit()
    
    return {
        "project_id": project_id,
        "quote": moment.quotable_text,
        "quote_card": quote_card
    }


@router.get("/story-suggestions/{project_id}")
async def get_story_suggestions(
    project_id: str,
    db: Session = Depends(get_db)
):
    """
    Get story-based clip suggestions for manual editing.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get or generate story analysis
    story_analysis = project.metadata.get('story_analysis', {}) if project.metadata else {}
    
    if not story_analysis:
        transcript = db.query(Transcript).filter(Transcript.project_id == project_id).first()
        if transcript:
            transcript_result = {
                'full_text': transcript.full_text,
                'segments': transcript.segments
            }
            story_analysis = analyze_story_structure(transcript_result)
    
    return {
        "project_id": project_id,
        "beats": story_analysis.get('beats', []),
        "arcs": story_analysis.get('arcs', []),
        "clip_suggestions": story_analysis.get('clip_suggestions', [])
    }
