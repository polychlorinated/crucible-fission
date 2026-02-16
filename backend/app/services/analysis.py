"""Analysis service using Kimi for moment identification and text generation."""

import json
from typing import Dict, Any, List
from sqlalchemy.orm import Session
import httpx

from app.config import get_settings
from app.models import Moment, Asset

settings = get_settings()


async def analyze_transcript(transcript_result: Dict[str, Any], project_id: str, db: Session) -> List[Moment]:
    """
    Analyze transcript to identify key moments using Kimi.
    
    Returns:
        List of Moment objects
    """
    full_text = transcript_result["full_text"]
    segments = transcript_result["segments"]
    
    # Build prompt for Kimi
    prompt = f"""Analyze this testimonial transcript and identify key moments.

Transcript:
{full_text}

For each key moment, provide:
1. Start and end timestamps (approximate, in seconds)
2. Moment type: problem, solution, result, emotional_peak, or cta
3. Brief summary (1-2 sentences)
4. Sentiment score (-1.0 to 1.0)
5. Importance score (0.0 to 1.0)
6. Most quotable line from this moment
7. Quote quality score (0.0 to 1.0)

Return ONLY a JSON array with this exact structure:
[
  {{
    "start_time": 0.0,
    "end_time": 15.5,
    "moment_type": "problem",
    "summary": "Description of the moment",
    "sentiment_score": -0.5,
    "importance_score": 0.8,
    "quotable_text": "Exact quote from transcript",
    "quotable_score": 0.9
  }}
]

Identify 5-8 key moments that tell a complete story. Focus on the most impactful, emotional, and quotable segments."""

    # Call Kimi API
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.moonshot_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.moonshot_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "moonshot-v1-8k",  # or appropriate model
                    "messages": [
                        {"role": "system", "content": "You are an expert content analyst. Identify key moments in transcripts."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"}
                },
                timeout=60.0
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Parse the response
            content = result["choices"][0]["message"]["content"]
            moments_data = json.loads(content)
            
            # Ensure it's a list
            if isinstance(moments_data, dict) and "moments" in moments_data:
                moments_data = moments_data["moments"]
            elif not isinstance(moments_data, list):
                moments_data = [moments_data]
            
            # Create Moment objects
            moments = []
            for m_data in moments_data:
                moment = Moment(
                    project_id=project_id,
                    moment_type=m_data.get("moment_type", "general"),
                    start_time=m_data.get("start_time", 0),
                    end_time=m_data.get("end_time", 0),
                    transcript=m_data.get("quotable_text", ""),
                    summary=m_data.get("summary", ""),
                    sentiment_score=m_data.get("sentiment_score", 0),
                    importance_score=m_data.get("importance_score", 0.5),
                    quotable_text=m_data.get("quotable_text", ""),
                    quotable_score=m_data.get("quotable_score", 0.5)
                )
                db.add(moment)
                moments.append(moment)
            
            db.commit()
            return moments
            
    except Exception as e:
        print(f"Error analyzing transcript: {e}")
        # Fallback: create simple moments from transcript segments
        return await _create_fallback_moments(segments, project_id, db)


async def _create_fallback_moments(segments: List[Dict], project_id: str, db: Session) -> List[Moment]:
    """Create simple moments as fallback if AI analysis fails."""
    moments = []
    
    # Take every 30-second segment as a moment
    current_start = 0
    current_text = []
    
    for seg in segments:
        if seg["start"] - current_start > 30:
            # Save current moment
            if current_text:
                moment = Moment(
                    project_id=project_id,
                    moment_type="general",
                    start_time=current_start,
                    end_time=seg["start"],
                    transcript=" ".join(current_text),
                    summary="Key moment from transcript",
                    sentiment_score=0,
                    importance_score=0.5,
                    quotable_text=current_text[0] if current_text else "",
                    quotable_score=0.5
                )
                db.add(moment)
                moments.append(moment)
            
            current_start = seg["start"]
            current_text = []
        
        current_text.append(seg["text"])
    
    db.commit()
    return moments


async def generate_text_assets(moments: List[Moment], transcript_result: Dict[str, Any], project_id: str, db: Session):
    """Generate text assets (emails, social posts) from moments."""
    
    # Get top 3 most quotable moments
    top_moments = sorted(moments, key=lambda m: m.quotable_score or 0, reverse=True)[:3]
    
    # Generate quotable snippets asset
    for i, moment in enumerate(top_moments):
        asset = Asset(
            project_id=project_id,
            moment_id=moment.id,
            asset_type="quote_card",
            title=f"Quote {i+1}",
            content=moment.quotable_text,
            description=moment.summary,
            status="completed"
        )
        db.add(asset)
    
    # Generate email templates (simplified for MVP)
    if top_moments:
        best_moment = top_moments[0]
        
        email_asset = Asset(
            project_id=project_id,
            moment_id=best_moment.id,
            asset_type="email",
            title="Testimonial Email",
            content=f"""Subject: See what our clients are saying

Hi [First Name],

I wanted to share a quick note from one of our clients:

"{best_moment.quotable_text}"

{best_moment.summary}

If you're ready to experience similar results, let's talk.

Best regards,
[Your Name]""",
            status="completed"
        )
        db.add(email_asset)
        
        # Social media captions
        social_platforms = [
            ("twitter", best_moment.quotable_text[:280]),
            ("linkedin", f"Client feedback:\\n\\n\"{best_moment.quotable_text[:200]}...\"\\n\\nRead the full story [link]"),
            ("instagram", f"\"{best_moment.quotable_text[:150]}...\" \\n\\n#testimonial #clientlove #results")
        ]
        
        for platform, caption in social_platforms:
            asset = Asset(
                project_id=project_id,
                moment_id=best_moment.id,
                asset_type=f"social_post_{platform}",
                title=f"{platform.capitalize()} Caption",
                content=caption,
                status="completed"
            )
            db.add(asset)
    
    db.commit()
