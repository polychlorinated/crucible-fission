"""
Story Arc Detection Service
Identifies narrative structures in transcripts and builds logical story sequences.
"""

from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum

class StoryBeatType(Enum):
    HOOK = "hook"                    # Attention grabber
    PROBLEM = "problem"              # Pain point
    AGITATION = "agitation"          # Why it matters
    SOLUTION = "solution"            # The fix
    PROOF = "proof"                  # Results/evidence
    TRANSFORMATION = "transformation" # Before/after
    EMOTION = "emotion"              # Feeling/reaction
    CTA = "cta"                      # Call to action
    CONTEXT = "context"              # Background/setup

@dataclass
class StoryBeat:
    beat_type: StoryBeatType
    start_time: float
    end_time: float
    text: str
    importance: float
    keywords: List[str]

class StoryArcDetector:
    """Detect narrative arcs in transcript segments."""
    
    # Keywords that indicate each beat type
    BEAT_KEYWORDS = {
        StoryBeatType.HOOK: [
            "can't believe", "amazing", "incredible", "shocked", "blown away",
            "game changer", "life changing", "never thought", "best decision"
        ],
        StoryBeatType.PROBLEM: [
            "struggling", "problem", "difficult", "hard", "challenge",
            "issue", "concerned", "worried", "frustrated", "used to"
        ],
        StoryBeatType.AGITATION: [
            "costing", "losing", "wasting", "every day", "constantly",
            "always", "never", "tired of", "fed up"
        ],
        StoryBeatType.SOLUTION: [
            "found", "discovered", "started using", "switched to", "tried",
            "implemented", "decided to", "chose", "recommend"
        ],
        StoryBeatType.PROOF: [
            "increased", "decreased", "improved", "doubled", "tripled",
            "saved", "gained", "achieved", "percent", "%", "times", "results"
        ],
        StoryBeatType.TRANSFORMATION: [
            "before", "after", "now", "used to", "changed", "transformed",
            "completely", "totally", "entirely", "difference"
        ],
        StoryBeatType.EMOTION: [
            "love", "happy", "excited", "thrilled", "grateful", "relieved",
            "confident", "peace of mind", "comfortable", "trust"
        ],
        StoryBeatType.CTA: [
            "recommend", "suggest", "try", "check out", "look into",
            "worth it", "give it a shot", "you should"
        ],
        StoryBeatType.CONTEXT: [
            "my name", "i'm a", "we are", "our business", "been using",
            "for about", "since", "when we started"
        ]
    }
    
    def __init__(self):
        self.beat_scores = {}
    
    def classify_segment(self, segment: Dict) -> List[Tuple[StoryBeatType, float]]:
        """
        Classify a transcript segment into story beat types.
        Returns list of (beat_type, confidence_score) tuples.
        """
        text = segment.get('text', '').lower()
        scores = []
        
        for beat_type, keywords in self.BEAT_KEYWORDS.items():
            score = 0.0
            matched_keywords = []
            
            for keyword in keywords:
                if keyword in text:
                    score += 0.2
                    matched_keywords.append(keyword)
            
            # Bonus for multiple keyword matches
            if len(matched_keywords) >= 2:
                score += 0.3
            
            # Normalize to 0-1 range
            score = min(score, 1.0)
            
            if score > 0.2:  # Only include if reasonably confident
                scores.append((beat_type, score, matched_keywords))
        
        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return [(beat_type, score) for beat_type, score, _ in scores]
    
    def detect_story_beats(self, segments: List[Dict]) -> List[StoryBeat]:
        """
        Detect all story beats in transcript segments.
        """
        beats = []
        
        for segment in segments:
            classifications = self.classify_segment(segment)
            
            if classifications:
                # Take the highest confidence beat type
                best_type, best_score = classifications[0]
                
                beat = StoryBeat(
                    beat_type=best_type,
                    start_time=segment.get('start', 0),
                    end_time=segment.get('end', 0),
                    text=segment.get('text', ''),
                    importance=best_score,
                    keywords=[kw for _, _, kws in classifications for kw in kws]
                )
                beats.append(beat)
        
        # Sort by time
        beats.sort(key=lambda b: b.start_time)
        
        return beats
    
    def build_story_arcs(self, beats: List[StoryBeat]) -> List[Dict[str, Any]]:
        """
        Build complete story arcs from detected beats.
        Returns list of story structures with multiple beats.
        """
        arcs = []
        used_beats = set()  # Track which beats have been used in arcs
        
        # Look for Problem → Solution → Proof patterns (classic testimonial)
        for i, beat in enumerate(beats):
            if beat.beat_type == StoryBeatType.PROBLEM and i not in used_beats:
                arc_beats = [beat]
                used_beats.add(i)
                
                # Look for Solution within next 60 seconds
                for j in range(i + 1, min(i + 10, len(beats))):
                    if j in used_beats:
                        continue
                    next_beat = beats[j]
                    if next_beat.beat_type == StoryBeatType.SOLUTION:
                        arc_beats.append(next_beat)
                        used_beats.add(j)
                        # Look for Proof/Result after Solution
                        for k in range(j + 1, min(j + 5, len(beats))):
                            if k in used_beats:
                                continue
                            proof_beat = beats[k]
                            if proof_beat.beat_type in [StoryBeatType.PROOF, StoryBeatType.EMOTION]:
                                arc_beats.append(proof_beat)
                                used_beats.add(k)
                                break
                        break
                
                if len(arc_beats) >= 2:
                    duration = arc_beats[-1].end_time - arc_beats[0].start_time
                    if 10 <= duration <= 90:  # Reasonable story length
                        arcs.append({
                            'type': 'problem_solution',
                            'beats': arc_beats,
                            'duration': duration,
                            'score': sum(b.importance for b in arc_beats) / len(arc_beats) + len(arc_beats) * 0.1
                        })
        
        # Look for Hook → Proof/Emotion patterns (attention grabbers)
        for i, beat in enumerate(beats):
            if beat.beat_type == StoryBeatType.HOOK and i not in used_beats:
                arc_beats = [beat]
                used_beats.add(i)
                
                for j in range(i + 1, min(i + 6, len(beats))):
                    if j in used_beats:
                        continue
                    next_beat = beats[j]
                    if next_beat.beat_type in [StoryBeatType.PROOF, StoryBeatType.EMOTION, StoryBeatType.SOLUTION]:
                        arc_beats.append(next_beat)
                        used_beats.add(j)
                        break
                
                if len(arc_beats) >= 2:
                    duration = arc_beats[-1].end_time - arc_beats[0].start_time
                    if 5 <= duration <= 45:
                        arcs.append({
                            'type': 'hook_proof',
                            'beats': arc_beats,
                            'duration': duration,
                            'score': sum(b.importance for b in arc_beats) / len(arc_beats)
                        })
        
        # Look for Transformation arcs (Before → After → Emotion)
        for i, beat in enumerate(beats):
            if beat.beat_type == StoryBeatType.TRANSFORMATION and i not in used_beats:
                arc_beats = [beat]
                used_beats.add(i)
                
                for j in range(i + 1, min(i + 6, len(beats))):
                    if j in used_beats:
                        continue
                    next_beat = beats[j]
                    if next_beat.beat_type in [StoryBeatType.PROOF, StoryBeatType.EMOTION]:
                        arc_beats.append(next_beat)
                        used_beats.add(j)
                        break
                
                if len(arc_beats) >= 2:
                    duration = arc_beats[-1].end_time - arc_beats[0].start_time
                    if 5 <= duration <= 60:
                        arcs.append({
                            'type': 'transformation',
                            'beats': arc_beats,
                            'duration': duration,
                            'score': sum(b.importance for b in arc_beats) / len(arc_beats) + 0.15
                        })
        
        # Build emotional journey arcs (Emotion → Proof → CTA)
        for i, beat in enumerate(beats):
            if beat.beat_type == StoryBeatType.EMOTION and i not in used_beats:
                arc_beats = [beat]
                used_beats.add(i)
                
                for j in range(i + 1, min(i + 6, len(beats))):
                    if j in used_beats:
                        continue
                    next_beat = beats[j]
                    if next_beat.beat_type in [StoryBeatType.PROOF, StoryBeatType.CTA]:
                        arc_beats.append(next_beat)
                        used_beats.add(j)
                        break
                
                if len(arc_beats) >= 2:
                    duration = arc_beats[-1].end_time - arc_beats[0].start_time
                    if 5 <= duration <= 45:
                        arcs.append({
                            'type': 'emotional_journey',
                            'beats': arc_beats,
                            'duration': duration,
                            'score': sum(b.importance for b in arc_beats) / len(arc_beats)
                        })
        
        # Sort by score (highest quality first)
        arcs.sort(key=lambda a: a['score'], reverse=True)
        
        return arcs
    
    def generate_clip_suggestions(self, arcs: List[Dict]) -> List[Dict[str, Any]]:
        """
        Generate specific clip suggestions from story arcs.
        Creates stitched narratives that flow logically.
        """
        suggestions = []
        
        for arc in arcs[:3]:  # Top 3 arcs
            beats = arc['beats']
            arc_type = arc['type']
            
            # Calculate total duration
            total_duration = beats[-1].end_time - beats[0].start_time
            
            # Skip if too short or too long
            if total_duration < 5 or total_duration > 90:
                continue
            
            # Build narrative description based on arc type
            if arc_type == 'problem_solution':
                narrative_desc = f"Problem: {beats[0].text[:50]}... → Solution: {beats[1].text[:50]}..."
                if len(beats) > 2:
                    narrative_desc += f" → Result: {beats[2].text[:50]}..."
            elif arc_type == 'transformation':
                narrative_desc = f"Before/After: {beats[0].text[:50]}... → Impact: {beats[1].text[:50]}..."
            elif arc_type == 'hook_proof':
                narrative_desc = f"Hook: {beats[0].text[:50]}... → Proof: {beats[1].text[:50]}..."
            elif arc_type == 'emotional_journey':
                narrative_desc = f"Feeling: {beats[0].text[:50]}... → Outcome: {beats[1].text[:50]}..."
            else:
                narrative_desc = f"Story: {' → '.join([b.text[:40] + '...' for b in beats[:2]])}"
            
            # Create segments with calculated durations
            segments = []
            for beat in beats:
                duration = beat.end_time - beat.start_time
                # Cap individual segments to avoid too-long clips
                if duration > 30:
                    duration = 30
                segments.append((beat.start_time, duration))
            
            # Single stitched story clip (combines all beats)
            suggestions.append({
                'name': arc_type,
                'duration': sum(d for _, d in segments),
                'segments': segments,
                'description': narrative_desc,
                'purpose': self._get_purpose_for_duration(sum(d for _, d in segments)),
                'beats_used': [b.beat_type.value for b in beats],
                'narrative_flow': arc_type.replace('_', ' ').title()
            })
            
            # Also create individual beat clips for flexibility
            for i, beat in enumerate(beats):
                duration = min(beat.end_time - beat.start_time, 15)  # Cap at 15s
                suggestions.append({
                    'name': f"{arc_type}_beat_{i+1}",
                    'duration': duration,
                    'segments': [(beat.start_time, duration)],
                    'description': f"{beat.beat_type.value.title()}: {beat.text[:80]}...",
                    'purpose': f"Individual {beat.beat_type.value} moment",
                    'beats_used': [beat.beat_type.value],
                    'narrative_flow': 'individual'
                })
        
        # Sort by duration (shortest first for easier browsing)
        suggestions.sort(key=lambda x: x['duration'])
        
        return suggestions[:6]  # Return top 6 suggestions
    
    def _get_purpose_for_duration(self, duration: float) -> str:
        """Get recommended platform based on duration."""
        if duration <= 10:
            return "Social Hook - Instagram Story, TikTok Hook"
        elif duration <= 30:
            return "Short Story - Instagram Reel, TikTok, YouTube Short"
        elif duration <= 45:
            return "Medium Story - Facebook, LinkedIn, YouTube"
        else:
            return "Full Story - Website, Email, Presentations"


def analyze_story_structure(transcript_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point: analyze transcript and return story structure.
    """
    detector = StoryArcDetector()
    segments = transcript_result.get('segments', [])
    
    # Detect beats
    beats = detector.detect_story_beats(segments)
    
    # Build arcs
    arcs = detector.build_story_arcs(beats)
    
    # Generate suggestions
    suggestions = detector.generate_clip_suggestions(arcs)
    
    return {
        'beats_detected': len(beats),
        'arcs_identified': len(arcs),
        'beats': [
            {
                'type': b.beat_type.value,
                'start': b.start_time,
                'end': b.end_time,
                'text': b.text[:100],
                'importance': b.importance
            }
            for b in beats[:10]  # Top 10 beats
        ],
        'arcs': [
            {
                'type': arc['type'],
                'duration': arc['duration'],
                'score': arc['score'],
                'beats': [b.beat_type.value for b in arc['beats']]
            }
            for arc in arcs[:5]
        ],
        'clip_suggestions': suggestions
    }
