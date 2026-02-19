"""Analysis service using Kimi for moment identification and text generation."""

import json
import re
from typing import Dict, Any, List, Tuple
from sqlalchemy.orm import Session
import httpx

from app.config import get_settings
from app.models import Moment, Asset

settings = get_settings()

# Keywords that indicate valuable content vs filler/interviewer
RESULT_KEYWORDS = [
    'increased', 'decreased', 'improved', 'doubled', 'tripled', 'grew', 'saved',
    'more', 'less', 'better', 'faster', 'easier', 'results', 'outcome', 'roi',
    'revenue', 'sales', 'leads', 'conversion', 'percent', '%', 'times', 'x '
]

EMOTIONAL_KEYWORDS = [
    'love', 'amazing', 'incredible', 'fantastic', 'best', 'changed', 'transformed',
    'thank', 'grateful', 'excited', 'happy', 'recommend', 'obsessed', 'game changer',
    'blown away', 'shocked', 'surprised', 'impressed', 'worth it'
]

FILLER_WORDS = [
    'um', 'uh', 'like', 'you know', 'sort of', 'kind of', 'basically',
    'literally', 'actually', 'honestly', 'so yeah', 'right', 'okay'
]

QUESTION_INDICATORS = [
    'can you', 'could you', 'would you', 'will you', 'do you', 'did you',
    'what', 'when', 'where', 'why', 'how', 'tell me', 'explain'
]


def calculate_segment_quality(segment: Dict) -> Tuple[float, str]:
    """
    Calculate quality score for a segment.
    Returns (score, reason) where higher score = better content.
    """
    text = segment.get('text', '').strip()
    duration = segment.get('end', 0) - segment.get('start', 0)
    
    if not text:
        return 0.0, "empty"
    
    score = 0.0
    text_lower = text.lower()
    words = text.split()
    word_count = len(words)
    
    # Penalty: Too short (< 3 seconds)
    if duration < 3.0:
        return 0.1, "too_short"
    
    # Penalty: Too long (> 45 seconds, probably rambling)
    if duration > 45.0:
        score -= 0.2
    
    # Penalty: Ends with question mark (interviewer question)
    if text.endswith('?'):
        return 0.1, "is_question"
    
    # Penalty: Starts with question words (likely question)
    first_words = ' '.join(words[:3]).lower()
    if any(q in first_words for q in QUESTION_INDICATORS):
        return 0.15, "starts_with_question"
    
    # Penalty: High filler word ratio
    filler_count = sum(text_lower.count(filler) for filler in FILLER_WORDS)
    filler_ratio = filler_count / max(word_count, 1)
    if filler_ratio > 0.15:
        score -= 0.3
    
    # Bonus: Contains result keywords (specific outcomes)
    result_matches = sum(1 for keyword in RESULT_KEYWORDS if keyword in text_lower)
    score += result_matches * 0.25
    
    # Bonus: Contains emotional keywords (enthusiasm)
    emotion_matches = sum(1 for keyword in EMOTIONAL_KEYWORDS if keyword in text_lower)
    score += emotion_matches * 0.2
    
    # Bonus: Substantial duration (5-20 seconds is ideal)
    if 5.0 <= duration <= 20.0:
        score += 0.3
    
    # Bonus: Good word density (not too sparse = not too much silence)
    words_per_second = word_count / max(duration, 1)
    if 2.0 <= words_per_second <= 4.0:
        score += 0.2
    
    # Bonus: Contains numbers (specific results)
    if re.search(r'\d+%|\d+ percent|\d+ x|\d+ times|\$\d+', text):
        score += 0.4
    
    return max(score, 0.0), "quality"


def identify_best_segments(segments: List[Dict], max_segments: int = 5) -> List[Dict]:
    """
    Identify the best segments using heuristics.
    Returns segments sorted by quality score.
    """
    scored_segments = []
    
    for seg in segments:
        score, reason = calculate_segment_quality(seg)
        
        if score > 0.3:  # Only consider segments above quality threshold
            scored_segments.append((score, seg))
            print(f"[Quality] Segment at {seg.get('start', 0):.1f}s scored {score:.2f} ({reason}): {seg.get('text', '')[:60]}...")
        else:
            print(f"[Quality] Skipped segment at {seg.get('start', 0):.1f}s (score {score:.2f}, {reason})")
    
    # Sort by score descending
    scored_segments.sort(key=lambda x: x[0], reverse=True)
    
    # Return top segments
    return [seg for score, seg in scored_segments[:max_segments]]


async def analyze_transcript(transcript_result: Dict[str, Any], project_id: str, db: Session) -> List[Moment]:
    """
    Analyze transcript to identify key moments using Kimi.
    
    Returns:
        List of Moment objects
    """
    full_text = transcript_result["full_text"]
    segments = transcript_result["segments"]
    
    # Build improved prompt for Kimi
    prompt = f"""Analyze this testimonial interview transcript and identify 3-5 most valuable moments from the SUBJECT (not the interviewer).

TRANSCRIPT:
{full_text}

IMPORTANT CONTEXT:
- This is an INTERVIEW with at least two people
- The INTERVIEWER asks questions and prompts
- The SUBJECT is the person giving the testimonial/sharing their experience
- We want ONLY the SUBJECT's valuable answers, NOT interviewer questions

IDENTIFY moments where the SUBJECT provides:
✓ Specific results, numbers, or outcomes ("increased by 50%", "saved $10k")
✓ Emotional reactions or enthusiasm ("I was blown away", "game changer")
✓ Before/after transformation stories
✓ Specific recommendations or endorsements
✓ Problem descriptions followed by solution benefits

EXCLUDE:
✗ Interviewer questions (text ending with "?")
✗ Interviewer prompts ("Tell me about...", "Can you explain...")
✗ Short acknowledgments ("Yeah", "Sure", "Okay")
✗ Small talk or introductions
✗ Segments under 5 seconds
✗ Segments with mostly filler words (um, uh, like, you know)

For each moment, provide:
1. Start and end timestamps (in seconds) - be precise
2. Moment type: problem, solution, result, emotional_peak, or cta
3. Brief summary focusing on the VALUE provided
4. Sentiment score (-1.0 to 1.0)
5. Importance score (0.0 to 1.0) - higher for specific results/numbers
6. The most quotable line (the "money quote" - the most impactful single sentence)
7. Quote quality score (0.0 to 1.0)

Return ONLY a JSON array:
[
  {{
    "start_time": 45.2,
    "end_time": 58.5,
    "moment_type": "result",
    "summary": "Subject describes 50% increase in leads after using product",
    "sentiment_score": 0.8,
    "importance_score": 0.95,
    "quotable_text": "We saw our leads double within the first month",
    "quotable_score": 0.9
  }}
]

PRIORITIZE: Specific numbers > emotional praise > general statements > questions"""

    # Call Kimi API
    try:
        print("[Analysis] Calling Kimi API for moment analysis...")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.moonshot_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.moonshot_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "moonshot-v1-8k",
                    "messages": [
                        {"role": "system", "content": "You are an expert content analyst specializing in testimonial videos. Your job is to identify the most valuable, quotable moments where the subject provides specific results and emotional reactions."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2,
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
            
            print(f"[Analysis] Kimi returned {len(moments_data)} moments")
            
            # Validate and filter moments
            moments = []
            for m_data in moments_data:
                start_time = m_data.get("start_time", 0)
                end_time = m_data.get("end_time", 0)
                quotable_text = m_data.get("quotable_text", "")
                
                # Skip if it looks like a question
                if quotable_text.strip().endswith('?'):
                    print(f"[Analysis] Skipping moment with question: {quotable_text[:50]}...")
                    continue
                
                # Skip if too short
                if end_time - start_time < 3.0:
                    print(f"[Analysis] Skipping short moment ({end_time - start_time:.1f}s)")
                    continue
                
                moment = Moment(
                    project_id=project_id,
                    moment_type=m_data.get("moment_type", "general"),
                    start_time=start_time,
                    end_time=end_time,
                    transcript=quotable_text,
                    summary=m_data.get("summary", ""),
                    sentiment_score=m_data.get("sentiment_score", 0),
                    importance_score=m_data.get("importance_score", 0.5),
                    quotable_text=quotable_text,
                    quotable_score=m_data.get("quotable_score", 0.5)
                )
                db.add(moment)
                moments.append(moment)
                print(f"[Analysis] Created moment: {quotable_text[:60]}...")
            
            db.commit()
            
            # If Kimi returned good moments, use them
            if len(moments) >= 2:
                print(f"[Analysis] Successfully created {len(moments)} moments from Kimi")
                return moments
            else:
                print(f"[Analysis] Kimi returned insufficient moments ({len(moments)}), using fallback")
                
    except Exception as e:
        print(f"[Analysis] Error calling Kimi API: {e}")
    
    # Fallback: use heuristic-based segment selection
    print("[Analysis] Using heuristic fallback for moment selection...")
    return await _create_fallback_moments(segments, project_id, db)


async def _create_fallback_moments(segments: List[Dict], project_id: str, db: Session) -> List[Moment]:
    """Create quality moments using heuristics when AI analysis fails."""
    moments = []
    
    # Identify best segments using quality heuristics
    best_segments = identify_best_segments(segments, max_segments=3)
    
    if not best_segments:
        print("[Analysis] WARNING: No quality segments found! Using top 3 by duration.")
        # Last resort: use longest segments
        sorted_segments = sorted(segments, key=lambda s: s.get('end', 0) - s.get('start', 0), reverse=True)
        best_segments = sorted_segments[:3]
    
    # Create moments from best segments
    for i, seg in enumerate(best_segments):
        text = seg.get('text', '').strip()
        duration = seg.get('end', 0) - seg.get('start', 0)
        
        # Calculate quality score for importance weighting
        quality_score, _ = calculate_segment_quality(seg)
        
        moment = Moment(
            project_id=project_id,
            moment_type="general",
            start_time=seg.get('start', 0),
            end_time=seg.get('end', 0),
            transcript=text,
            summary=f"Key insight ({duration:.0f}s): {text[:80]}..." if len(text) > 80 else f"Key insight: {text}",
            sentiment_score=0.3,
            importance_score=min(quality_score, 1.0),
            quotable_text=text,
            quotable_score=min(quality_score, 1.0)
        )
        db.add(moment)
        moments.append(moment)
        print(f"[Analysis] Created quality moment {i+1} (score {quality_score:.2f}, {duration:.1f}s): {text[:50]}...")
    
    db.commit()
    print(f"[Analysis] Fallback created {len(moments)} quality moments")
    return moments


async def generate_text_assets(moments: List[Moment], transcript_result: Dict[str, Any], project_id: str, db: Session):
    """Generate text assets (emails, social posts) from moments."""
    
    # Filter to moments with actual quotable content
    valid_moments = [m for m in moments if m.quotable_text and len(m.quotable_text.strip()) > 10]
    
    if not valid_moments:
        print("[Analysis] WARNING: No valid moments with quotable text found!")
        return
    
    # Get top 3 most quotable moments
    top_moments = sorted(valid_moments, key=lambda m: m.quotable_score or 0, reverse=True)[:3]
    
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
        print(f"[Analysis] Created quote card {i+1}: {moment.quotable_text[:50]}...")
    
    # Generate email templates
    best_moment = top_moments[0]
    
    email_asset = Asset(
        project_id=project_id,
        moment_id=best_moment.id,
        asset_type="email",
        title="Testimonial Email",
        content=f"""Subject: The results speak for themselves

Hi [First Name],

I wanted to share what one of our clients recently shared:

"{best_moment.quotable_text}"

{best_moment.summary}

Ready to see similar results? Let's talk.

Best regards,
[Your Name]""",
        status="completed"
    )
    db.add(email_asset)
    
    # Social media captions - tailored to platform
    social_platforms = [
        ("twitter", f'"{best_moment.quotable_text[:250]}" - Real client feedback'),
        ("linkedin", f"Client Spotlight:\n\n\"{best_moment.quotable_text[:180]}...\"\n\n{best_moment.summary[:100]}\n\n#ClientSuccess #Results #Testimonial"),
        ("instagram", f"\"{best_moment.quotable_text[:120]}...\" 💬\n\nReal results from real clients ✨\n\n#testimonial #clientlove #results #transformation")
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
    print(f"[Analysis] Generated text assets from {len(top_moments)} moments")
