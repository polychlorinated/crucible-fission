"""
Visual Content Generation Service
Generates images for content with priority: original > AI illustrations > stock
"""

import os
from typing import Dict, Any, List, Optional
import httpx
from dataclasses import dataclass

@dataclass
class VisualAsset:
    asset_type: str  # 'original', 'ai_illustration', 'stock', 'quote_card'
    source_url: str
    local_path: Optional[str]
    alt_text: str
    keywords: List[str]
    confidence: float  # How well it matches the content

class VisualContentGenerator:
    """Generate visual assets for content with priority-based sourcing."""
    
    def __init__(self, openai_api_key: str = None, unsplash_key: str = None):
        from app.config import get_settings
        settings = get_settings()
        self.openai_api_key = openai_api_key or settings.openai_api_key or os.getenv('OPENAI_API_KEY')
        self.unsplash_key = unsplash_key or settings.unsplash_access_key or os.getenv('UNSPLASH_ACCESS_KEY')
    
    def extract_visual_keywords(self, text: str, context: Dict = None) -> List[str]:
        """
        Extract visual keywords from text content.
        Returns prioritized list of search terms.
        """
        text_lower = text.lower()
        keywords = {
            'primary': [],      # Main subjects
            'secondary': [],    # Supporting elements
            'emotional': [],    # Mood/feeling
            'action': []        # What's happening
        }
        
        # Primary subjects (nouns/entities)
        subject_indicators = {
            'dog': ['dog', 'puppy', 'canine', 'pet', 'dogs'],
            'person': ['i', 'we', 'my', 'client', 'customer', 'owner'],
            'vehicle': ['van', 'car', 'truck'],
            'location': ['home', 'house', 'office', 'facility']
        }
        
        for subject, indicators in subject_indicators.items():
            if any(ind in text_lower for ind in indicators):
                keywords['primary'].append(subject)
        
        # Emotional keywords
        emotion_map = {
            'joy': ['happy', 'excited', 'thrilled', 'joy', 'wagging', 'smiling'],
            'trust': ['confident', 'comfortable', 'trust', 'safe', 'relaxed'],
            'love': ['love', 'adore', 'obsessed', 'amazing', 'best'],
            'relief': ['relieved', 'peace of mind', 'finally', 'no longer worried']
        }
        
        for emotion, indicators in emotion_map.items():
            if any(ind in text_lower for ind in indicators):
                keywords['emotional'].append(emotion)
        
        # Action keywords
        action_indicators = {
            'jumping': ['jump', 'hop', 'leap'],
            'playing': ['play', 'run', 'chase'],
            'interacting': ['hug', 'pet', 'cuddle', 'pick up'],
            'transporting': ['van', 'pick up', 'drop off', 'ride']
        }
        
        for action, indicators in action_indicators.items():
            if any(ind in text_lower for ind in indicators):
                keywords['action'].append(action)
        
        # Secondary elements (context)
        if 'van' in text_lower or 'pick up' in text_lower:
            keywords['secondary'].extend(['van', 'transportation'])
        if 'tail' in text_lower or 'wagging' in text_lower:
            keywords['secondary'].extend(['tail', 'happy dog'])
        
        # Build search queries in priority order
        search_queries = []
        
        # Primary + action combinations
        for primary in keywords['primary']:
            for action in keywords['action']:
                search_queries.append(f"{action} {primary}")
        
        # Emotional + primary
        for emotion in keywords['emotional']:
            for primary in keywords['primary']:
                search_queries.append(f"{emotion} {primary}")
        
        # Add secondary context
        if keywords['secondary']:
            search_queries.append(' '.join(keywords['secondary'][:2]))
        
        # Fallback to general
        if keywords['primary']:
            search_queries.append(keywords['primary'][0])
        
        return list(dict.fromkeys(search_queries))  # Remove duplicates
    
    async def search_stock_images(self, query: str, count: int = 3) -> List[VisualAsset]:
        """
        Search Unsplash for stock images.
        Returns list of VisualAsset objects.
        """
        if not self.unsplash_key:
            print("[Visual] No Unsplash API key configured")
            return []
        
        assets = []
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.unsplash.com/search/photos",
                    headers={"Authorization": f"Client-ID {self.unsplash_key}"},
                    params={
                        "query": query,
                        "per_page": count,
                        "orientation": "landscape"
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    for photo in data.get('results', []):
                        asset = VisualAsset(
                            asset_type='stock',
                            source_url=photo['urls']['regular'],
                            local_path=None,
                            alt_text=photo.get('alt_description', query),
                            keywords=query.split(),
                            confidence=0.6  # Stock is lower confidence
                        )
                        assets.append(asset)
                        
        except Exception as e:
            print(f"[Visual] Unsplash search error: {e}")
        
        return assets
    
    async def generate_ai_illustration(self, prompt: str, style: str = "whimsical illustration") -> Optional[VisualAsset]:
        """
        Generate AI illustration using DALL-E.
        Style: Illustration (not photorealistic) as per user preference.
        """
        if not self.openai_api_key:
            print("[Visual] No OpenAI API key configured")
            return None
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/images/generations",
                    headers={
                        "Authorization": f"Bearer {self.openai_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "dall-e-3",
                        "prompt": f"{prompt}. Style: {style}. Flat illustration style, not photorealistic. Friendly, warm colors.",
                        "size": "1024x1024",
                        "quality": "standard",
                        "n": 1
                    },
                    timeout=60.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    image_url = data['data'][0]['url']
                    
                    return VisualAsset(
                        asset_type='ai_illustration',
                        source_url=image_url,
                        local_path=None,
                        alt_text=prompt,
                        keywords=prompt.split(),
                        confidence=0.9  # High confidence for custom generation
                    )
                else:
                    print(f"[Visual] DALL-E error: {response.status_code} - {response.text}")
                    
        except Exception as e:
            print(f"[Visual] AI generation error: {e}")
        
        return None
    
    def build_ai_prompt(self, content: str, context: Dict = None) -> str:
        """
        Build an AI illustration prompt from content.
        """
        keywords = self.extract_visual_keywords(content, context)
        
        # Build scene description
        scene_elements = []
        
        if 'dog' in str(keywords).lower():
            scene_elements.append("a happy dog")
        
        if any('jump' in k for k in keywords):
            scene_elements.append("jumping excitedly")
        
        if 'van' in str(keywords).lower() or 'transport' in str(keywords).lower():
            scene_elements.append("near a friendly dog transport van")
        
        if 'happy' in str(keywords).lower() or 'joy' in str(keywords).lower():
            scene_elements.append("with tail wagging")
        
        # Build the prompt
        base_prompt = " ".join(scene_elements) if scene_elements else "a friendly pet care scene"
        
        # Add style modifiers (illustration, not photo)
        style_modifiers = (
            "warm, friendly illustration style. "
            "Bright, cheerful colors. "
            "Children's book illustration aesthetic. "
            "Clean lines, flat design, not photorealistic. "
            "White background or simple environment."
        )
        
        full_prompt = f"{base_prompt}. {style_modifiers}"
        
        return full_prompt
    
    async def generate_content_visuals(
        self,
        content: str,
        content_type: str = 'social_post',
        client_assets: List[str] = None,  # URLs to client's original images
        context: Dict = None
    ) -> Dict[str, Any]:
        """
        Generate visual assets for content with priority:
        1. Client's original images (if provided)
        2. AI-generated illustrations
        3. Stock images (fallback)
        """
        results = {
            'primary_visual': None,
            'alternatives': [],
            'sourcing': 'none',
            'keywords': [],
            'ai_prompt': None
        }
        
        # Step 1: Check for client original images
        if client_assets and len(client_assets) > 0:
            # Use first client image as primary
            results['primary_visual'] = VisualAsset(
                asset_type='original',
                source_url=client_assets[0],
                local_path=None,
                alt_text='Client provided image',
                keywords=[],
                confidence=1.0  # Highest confidence - client chose it
            )
            results['sourcing'] = 'original'
            results['alternatives'] = [
                VisualAsset(
                    asset_type='original',
                    source_url=url,
                    local_path=None,
                    alt_text='Client provided image',
                    keywords=[],
                    confidence=1.0
                )
                for url in client_assets[1:3]  # Up to 2 more
            ]
            return results
        
        # Step 2: Generate AI illustration
        ai_prompt = self.build_ai_prompt(content, context)
        results['ai_prompt'] = ai_prompt
        
        ai_image = await self.generate_ai_illustration(ai_prompt)
        
        if ai_image:
            results['primary_visual'] = ai_image
            results['sourcing'] = 'ai_illustration'
            
            # Generate 2 variations
            for variation in ['different angle', 'different color palette']:
                var_prompt = f"{ai_prompt} {variation}"
                var_image = await self.generate_ai_illustration(var_prompt)
                if var_image:
                    results['alternatives'].append(var_image)
            
            return results
        
        # Step 3: Fallback to stock images
        keywords = self.extract_visual_keywords(content, context)
        results['keywords'] = keywords
        
        if keywords:
            stock_images = await self.search_stock_images(keywords[0], count=3)
            if stock_images:
                results['primary_visual'] = stock_images[0]
                results['alternatives'] = stock_images[1:]
                results['sourcing'] = 'stock'
        
        return results
    
    async def generate_quote_card_visuals(
        self,
        quote: str,
        brand_colors: Dict = None,
        logo_url: str = None,
        client_assets: List[str] = None
    ) -> Dict[str, Any]:
        """
        Generate visuals specifically for quote cards.
        Returns background image + layout suggestions.
        """
        brand_colors = brand_colors or {
            'primary': '#2C5F2D',      # Default: Campbell green
            'secondary': '#97BC62',    # Light green
            'text': '#FFFFFF',
            'accent': '#FFB347'        # Warm orange
        }
        
        # Get visual for the quote
        visuals = await self.generate_content_visuals(
            content=quote,
            content_type='quote_card',
            client_assets=client_assets
        )
        
        # Build quote card specification
        quote_card = {
            'background_image': visuals['primary_visual'].source_url if visuals['primary_visual'] else None,
            'sourcing': visuals['sourcing'],
            'layout': {
                'quote_position': 'center',
                'quote_style': {
                    'font_size': 'large',
                    'color': brand_colors['text'],
                    'text_shadow': True
                },
                'attribution': {
                    'position': 'bottom_right',
                    'style': 'italic',
                    'color': brand_colors['secondary']
                },
                'branding': {
                    'logo_position': 'top_left' if logo_url else None,
                    'logo_url': logo_url,
                    'accent_color': brand_colors['accent']
                }
            },
            'alternatives': [
                {
                    'background_image': alt.source_url,
                    'sourcing': alt.asset_type
                }
                for alt in visuals['alternatives']
            ],
            'ai_prompt': visuals.get('ai_prompt')
        }
        
        return quote_card


async def test_visual_generation():
    """Test the visual generation system."""
    generator = VisualContentGenerator()
    
    # Test with Campbell K9s quote
    quote = "But I think since sending him to Campbell's canines, I've just seen him be just so excited. Like they pick him up in the van and his tails wagging, he jumps right in."
    
    keywords = generator.extract_visual_keywords(quote)
    print("Keywords:", keywords)
    
    ai_prompt = generator.build_ai_prompt(quote)
    print("AI Prompt:", ai_prompt)
    
    # Test without client assets (should use AI)
    results = await generator.generate_content_visuals(quote)
    print("Results:", results)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_visual_generation())
