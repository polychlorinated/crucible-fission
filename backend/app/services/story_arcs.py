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
        
        # Look for Problem → Solution → Proof patterns
        for i, beat in enumerate(beats):
            if beat.beat_type == StoryBeatType.PROBLEM:
                # Look for following Solution and Proof
                arc_beats = [beat]
                
                for j in range(i + 1, min(i + 5, len(beats))):
                    next_beat = beats[j]
                    if next_beat.beat_type in [StoryBeatType.SOLUTION, StoryBeatType.PROOF, 
                                               StoryBeatType.TRANSFORMATION, StoryBeatType.EMOTION]:
                        arc_beats.append(next_beat)
                
                if len(arc_beats) >= 2:  # Need at least problem + something
                    arcs.append({
                        'type': 'problem_solution',
                        'beats': arc_beats,
                        'duration': arc_beats[-1].end_time - arc_beats[0].start_time,
                        'score': sum(b.importance for b in arc_beats) / len(arc_beats)
                    })
        
        # Look for Hook → Proof → CTA patterns (good for short ads)
        for i, beat in enumerate(beats):
            if beat.beat_type == StoryBeatType.HOOK:
                arc_beats = [beat]
                
                for j in range(i + 1, min(i + 4, len(beats))):
                    next_beat = beats[j]
                    if next_beat.beat_type in [StoryBeatType.PROOF, StoryBeatType.EMOTION, StoryBeatType.CTA]:
                        arc_beats.append(next_beat)
                
                if len(arc_beats) >= 2:
                    arcs.append({
                        'type': 'hook_proof',
                        'beats': arc_beats,
                        'duration': arc_beats[-1].end_time - arc_beats[0].start_time,
                        'score': sum(b.importance for b in arc_beats) / len(arc_beats)
                    })
        
        # Look for Transformation arcs (Before → After → Emotion)
        for i, beat in enumerate(beats):
            if beat.beat_type == StoryBeatType.TRANSFORMATION:
                arc_beats = [beat]
                
                for j in range(i + 1, min(i + 4, len(beats))):
                    next_beat = beats[j]
                    if next_beat.beat_type in [StoryBeatType.PROOF, StoryBeatType.EMOTION]:
                        arc_beats.append(next_beat)
                
                if len(arc_beats) >= 2:
                    arcs.append({
                        'type': 'transformation',
                        'beats': arc_beats,
                        'duration': arc_beats[-1].end_time - arc_beats[0].start_time,
                        'score': sum(b.importance for b in arc_beats) / len(arc_beats)
                    })
        
        # Sort by score
        arcs.sort(key=lambda a: a['score'], reverse=True)
        
        return arcs
    
    def generate_clip_suggestions(self, arcs: List[Dict]) -> List[Dict[str, Any]]:
        """
        Generate specific clip suggestions from story arcs.
        """
        suggestions = []
        
        for arc in arcs[:3]:  # Top 3 arcs
            beats = arc['beats']
            
            # Micro hook (first beat only)
            if beats:
                suggestions.append({
                    'name': f"{arc['type']}_hook",
                    'duration': beats[0].end_time - beats[0].start_time,
                    'segments': [(beats[0].start_time, beats[0].end_time)],
                    'description': f"Hook: {beats[0].text[:80]}...",
                    'purpose': 'Social media hook (5-10s)',
                    'beats_used': [beats[0].beat_type.value]
                })
            
            # Short story (first 2 beats)
            if len(beats) >= 2:
                suggestions.append({
                    'name': f"{arc['type']}_short",
                    'duration': beats[1].end_time - beats[0].start_time,
                    'segments': [(beats[0].start_time, beats[0].end_time),
                                (beats[1].start_time, beats[1].end_time)],
                    'description': f"{beats[0].beat_type.value.title()}: {beats[0].text[:60]}... → {beats[1].beat_type.value.title()}: {beats[1].text[:60]}...",
                    'purpose': 'Instagram Reel / TikTok (15-30s)',
                    'beats_used': [b.beat_type.value for b in beats[:2]]
                })
            
            # Medium story (all beats)
            if len(beats) >= 3:
                suggestions.append({
                    'name': f"{arc['type']}_medium",
                    'duration': beats[-1].end_time - beats[0].start_time,
                    'segments': [(b.start_time, b.end_time) for b in beats],
                    'description': f"Complete {arc['type'].replace('_', ' ').title()} story with {len(beats)} beats",
                    'purpose': 'YouTube Short / Facebook (30-60s)',
                    'beats_used': [b.beat_type.value for b in beats]
                })
        
        return suggestions


def analyze_story_structure(transcript_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point: analyze transcript and return story structure.
    """
    detector = StoryArcDetector()
    segments = transcript_result.get('segments', [])
    
    # Detect beats
    beats = detector.detect_story_beats(segments)
    
    # Build arcs
    arcs = detector.build_story_beats(beats)
    
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
