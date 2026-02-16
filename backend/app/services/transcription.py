"""Transcription service using self-hosted Whisper."""

import os
from typing import Dict, Any
from faster_whisper import WhisperModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Transcript

settings = get_settings()

# Initialize model (will download on first run if not present)
_model = None

def get_model():
    """Get or initialize Whisper model."""
    global _model
    if _model is None:
        print(f"Loading Whisper model: {settings.whisper_model}")
        _model = WhisperModel(
            settings.whisper_model,
            device="cpu",
            compute_type="int8"
        )
    return _model


async def transcribe_video(video_path: str, project_id: str, db: Session) -> Dict[str, Any]:
    """
    Transcribe a video file using Whisper.
    
    Returns:
        Dict with full_text, segments, language
    """
    model = get_model()
    
    # Extract audio first (Whisper works better with audio files)
    audio_path = video_path.replace('.mp4', '_audio.wav')
    
    # Use ffmpeg to extract audio
    import subprocess
    cmd = [
        'ffmpeg',
        '-i', video_path,
        '-vn',  # No video
        '-acodec', 'pcm_s16le',  # PCM 16-bit
        '-ar', '16000',  # 16kHz (Whisper's preferred sample rate)
        '-ac', '1',  # Mono
        '-y',  # Overwrite
        audio_path
    ]
    
    subprocess.run(cmd, capture_output=True, check=True)
    
    try:
        # Transcribe
        segments, info = model.transcribe(audio_path, beam_size=5)
        
        # Convert to list and build full text
        segment_list = []
        full_text_parts = []
        
        for segment in segments:
            seg_dict = {
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip()
            }
            segment_list.append(seg_dict)
            full_text_parts.append(segment.text.strip())
        
        full_text = " ".join(full_text_parts)
        
        # Save to database
        transcript = Transcript(
            project_id=project_id,
            full_text=full_text,
            language=info.language,
            segments=segment_list
        )
        db.add(transcript)
        db.commit()
        
        result = {
            "transcript_id": str(transcript.id),
            "full_text": full_text,
            "language": info.language,
            "segments": segment_list,
            "duration": segment_list[-1]["end"] if segment_list else 0
        }
        
        return result
        
    finally:
        # Clean up audio file
        if os.path.exists(audio_path):
            os.remove(audio_path)
