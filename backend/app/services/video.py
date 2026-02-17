"""Video processing service using FFmpeg."""

import os
import subprocess
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Asset, Moment

settings = get_settings()


def get_video_duration(video_path: str) -> int:
    """Get video duration in seconds using ffprobe."""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return int(float(result.stdout.strip()))
    except:
        return 0


async def normalize_video(video_path: str, output_path: str) -> bool:
    """Normalize video to standard H.264/AAC format for reliable processing."""
    import asyncio
    
    cmd = [
        'ffmpeg',
        '-y',
        '-i', video_path,
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-crf', '23',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-movflags', '+faststart',
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Video normalization failed: {result.stderr[:500]}")
        return False
    return True


async def extract_moment_clips(moments: List[Moment], video_path: str, project_id: str, db: Session):
    """Extract video clips for each moment."""
    
    output_dir = os.path.join(settings.temp_dir, str(project_id), "clips")
    os.makedirs(output_dir, exist_ok=True)
    
    # First, normalize the input video to ensure codec compatibility
    normalized_path = os.path.join(settings.temp_dir, str(project_id), "normalized.mp4")
    print(f"Normalizing video: {video_path} -> {normalized_path}")
    
    if not await normalize_video(video_path, normalized_path):
        print("Failed to normalize video, trying with original...")
        normalized_path = video_path  # Fall back to original
    else:
        print("Video normalized successfully")
        video_path = normalized_path
    
    # Sort moments by importance
    sorted_moments = sorted(moments, key=lambda m: m.importance_score or 0, reverse=True)
    
    # Process top 5 moments
    for i, moment in enumerate(sorted_moments[:5]):
        try:
            # 15-second clip
            await extract_clip(
                video_path, 
                float(moment.start_time),
                15,
                os.path.join(output_dir, f"moment_{i+1}_15s.mp4"),
                moment,
                project_id,
                db
            )
            
            # 5-second micro-clip
            await extract_clip(
                video_path,
                float(moment.start_time),
                5,
                os.path.join(output_dir, f"moment_{i+1}_5s.mp4"),
                moment,
                project_id,
                db,
                is_micro=True
            )
            
            # Vertical version
            await create_vertical_version(
                video_path,
                float(moment.start_time),
                15,
                os.path.join(output_dir, f"moment_{i+1}_vertical.mp4"),
                moment,
                project_id,
                db
            )
            
        except Exception as e:
            print(f"Error extracting clip for moment {i+1}: {e}")
    
    # Clean up normalized file
    if normalized_path != video_path and os.path.exists(normalized_path):
        os.remove(normalized_path)


async def extract_clip(
    video_path: str, 
    start_time: float, 
    duration: int,
    output_path: str,
    moment: Moment,
    project_id: str,
    db: Session,
    is_micro: bool = False
):
    """Extract a single clip from video."""
    import asyncio
    
    # Ensure we don't exceed video bounds
    video_duration = get_video_duration(video_path)
    if start_time + duration > video_duration:
        duration = int(video_duration - start_time)
    
    # First, re-encode to ensure compatibility
    cmd = [
        'ffmpeg',
        '-y',
        '-i', video_path,
        '-ss', str(start_time),
        '-t', str(duration),
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-crf', '23',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-movflags', '+faststart',
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FFmpeg stderr: {result.stderr}")
        raise Exception(f"FFmpeg failed with code {result.returncode}: {result.stderr[:500]}")
    
    # Small delay to let memory settle between clips
    await asyncio.sleep(0.5)
    
    # Get file size
    file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
    
    # Create asset record
    asset_type = "video_micro" if is_micro else "video_clip"
    asset = Asset(
        project_id=project_id,
        moment_id=moment.id,
        asset_type=asset_type,
        title=f"{'Micro ' if is_micro else ''}Clip: {moment.summary[:50] if moment.summary else 'Moment'}",
        file_path=output_path,
        file_size_mb=file_size,
        duration_seconds=duration,
        dimensions="1280x720",
        format="mp4",
        status="completed"
    )
    db.add(asset)
    db.commit()


async def create_vertical_version(
    video_path: str,
    start_time: float,
    duration: int,
    output_path: str,
    moment: Moment,
    project_id: str,
    db: Session
):
    """Create vertical 9:16 version for mobile/social."""
    import asyncio
    
    video_duration = get_video_duration(video_path)
    if start_time + duration > video_duration:
        duration = int(video_duration - start_time)
    
    cmd = [
        'ffmpeg',
        '-y',
        '-i', video_path,
        '-ss', str(start_time),
        '-t', str(duration),
        '-vf', 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black',
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-crf', '23',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-movflags', '+faststart',
        output_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FFmpeg stderr: {result.stderr}")
        raise Exception(f"FFmpeg failed with code {result.returncode}: {result.stderr[:500]}")
    
    # Small delay to let memory settle
    await asyncio.sleep(0.5)
    
    file_size = os.path.getsize(output_path) / (1024 * 1024)
    
    asset = Asset(
        project_id=project_id,
        moment_id=moment.id,
        asset_type="video_vertical",
        title=f"Vertical: {moment.summary[:40] if moment.summary else 'Moment'}",
        file_path=output_path,
        file_size_mb=file_size,
        duration_seconds=duration,
        dimensions="1080x1920",
        format="mp4",
        status="completed"
    )
    db.add(asset)
    db.commit()


async def add_captions(video_path: str, captions_srt: str, output_path: str):
    """Add burned-in captions to video."""
    # TODO: Implement caption burn-in
    # For MVP, skip this and add in Phase 2
    pass
