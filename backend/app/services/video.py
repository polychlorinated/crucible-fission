"""Video processing service using FFmpeg."""

import os
import shutil
import subprocess
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Asset, Moment

settings = get_settings()

# Get ffmpeg path - prefer system ffmpeg, fallback to bundled
FFMPEG_PATH = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE_PATH = shutil.which("ffprobe") or "ffprobe"


def log_ffmpeg_error(result: subprocess.CompletedProcess, context: str):
    """Log FFmpeg errors for debugging."""
    print(f"[FFmpeg Error - {context}] Exit code: {result.returncode}")
    print(f"[FFmpeg Error - {context}] Stderr: {result.stderr[:1000] if result.stderr else 'None'}")
    print(f"[FFmpeg Error - {context}] Stdout: {result.stdout[:500] if result.stdout else 'None'}")


def get_video_duration(video_path: str) -> int:
    """Get video duration in seconds using ffprobe."""
    try:
        cmd = [
            FFPROBE_PATH,
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return int(float(result.stdout.strip()))
    except Exception as e:
        print(f"[Video] Failed to get duration for {video_path}: {e}")
        return 0


async def normalize_video(video_path: str, output_path: str) -> bool:
    """Normalize video to standard H.264/AAC format for reliable processing."""
    import asyncio

    print(f"[Video] Normalizing: {video_path} -> {output_path}")
    print(f"[Video] Input exists: {os.path.exists(video_path)}")
    print(f"[Video] Using FFmpeg: {FFMPEG_PATH}")

    if not os.path.exists(video_path):
        print(f"[Video] ERROR: Input file not found: {video_path}")
        return False

    cmd = [
        FFMPEG_PATH,
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
        log_ffmpeg_error(result, "normalize_video")
        return False

    print(f"[Video] Normalization successful: {output_path}")
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
    
    import asyncio
    
    # Sort moments by importance
    sorted_moments = sorted(moments, key=lambda m: m.importance_score or 0, reverse=True)
    
    # Process top 3 moments only (reduce memory pressure)
    for i, moment in enumerate(sorted_moments[:3]):
        try:
            # 15-second clip
            print(f"Processing moment {i+1}: 15s clip...")
            await extract_clip(
                video_path, 
                float(moment.start_time),
                15,
                os.path.join(output_dir, f"moment_{i+1}_15s.mp4"),
                moment,
                project_id,
                db
            )
            await asyncio.sleep(2)  # Longer delay between clips
            
            # 5-second micro-clip
            print(f"Processing moment {i+1}: 5s micro-clip...")
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
            await asyncio.sleep(2)
            
            # Skip vertical version on Railway free tier - requires too much memory
            # print(f"Processing moment {i+1}: vertical version...")
            # await create_vertical_version(
            #     video_path,
            #     float(moment.start_time),
            #     15,
            #     os.path.join(output_dir, f"moment_{i+1}_vertical.mp4"),
            #     moment,
            #     project_id,
            #     db
            # )
            # await asyncio.sleep(2)
            
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
    """Extract a single clip from video and upload to storage."""
    import asyncio
    from app.services.storage import upload_to_drive, create_folder
    
    # Ensure we don't exceed video bounds
    video_duration = get_video_duration(video_path)
    if start_time + duration > video_duration:
        duration = int(video_duration - start_time)
    
    # Low-memory encoding - aggressive settings for Railway free tier
    cmd = [
        FFMPEG_PATH,
        '-y',
        '-threads', '1',
        '-i', video_path,
        '-ss', str(start_time),
        '-t', str(duration),
        '-vf', 'scale=480:-2',  # Lower resolution to save memory
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-crf', '30',  # Higher CRF = lower quality but much faster
        '-x264-params', 'threads=1:lookahead-threads=1',  # Force x264 to use 1 thread
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-b:a', '64k',
        '-movflags', '+faststart',
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log_ffmpeg_error(result, f"extract_clip_{duration}s")
        raise Exception(f"FFmpeg failed with code {result.returncode}")
    
    # Small delay to let memory settle between clips
    await asyncio.sleep(0.5)
    
    # Get file size
    file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
    
    # Create asset record first (pending status)
    asset_type = "video_micro" if is_micro else "video_clip"
    asset = Asset(
        project_id=project_id,
        moment_id=moment.id,
        asset_type=asset_type,
        title=f"{'Micro ' if is_micro else ''}Clip: {moment.summary[:50] if moment.summary else 'Moment'}",
        file_path=output_path,
        file_size_mb=file_size,
        duration_seconds=duration,
        dimensions="480p",
        format="mp4",
        status="processing"
    )
    db.add(asset)
    db.commit()
    
    # Upload to Google Drive for persistent storage
    try:
        filename = os.path.basename(output_path)
        file_url = await upload_to_drive(output_path, filename)
        asset.file_url = file_url
        asset.status = "completed"
        db.commit()
        print(f"[Video] Uploaded to Drive: {file_url}")
    except Exception as e:
        print(f"[Video] Failed to upload to Drive: {e}")
        # Keep local file path - can still be downloaded from same instance
        asset.status = "completed"
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
    from app.services.storage import upload_to_drive
    
    video_duration = get_video_duration(video_path)
    if start_time + duration > video_duration:
        duration = int(video_duration - start_time)
    
    # Low-memory vertical version - 720p vertical to avoid OOM
    cmd = [
        FFMPEG_PATH,
        '-y',
        '-threads', '1',  # Limit to single thread
        '-i', video_path,
        '-ss', str(start_time),
        '-t', str(duration),
        '-vf', 'scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2:black',
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-crf', '28',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac',
        '-b:a', '96k',
        '-movflags', '+faststart',
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log_ffmpeg_error(result, "create_vertical_version")
        raise Exception(f"FFmpeg failed with code {result.returncode}")
    
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
        dimensions="720x1280",
        format="mp4",
        status="processing"
    )
    db.add(asset)
    db.commit()
    
    # Upload to Google Drive for persistent storage
    try:
        filename = os.path.basename(output_path)
        file_url = await upload_to_drive(output_path, filename)
        asset.file_url = file_url
        asset.status = "completed"
        db.commit()
        print(f"[Video] Uploaded vertical to Drive: {file_url}")
    except Exception as e:
        print(f"[Video] Failed to upload vertical to Drive: {e}")
        asset.status = "completed"
        db.commit()


async def add_captions(video_path: str, captions_srt: str, output_path: str):
    """Add burned-in captions to video."""
    # TODO: Implement caption burn-in
    # For MVP, skip this and add in Phase 2
    pass
