# Fission Reactor - Technical Specification
## v0.1 Decoupled Architecture

---

## SYSTEM ARCHITECTURE

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   React Frontend │────▶│  FastAPI Backend │────▶│   PostgreSQL    │
│   (Vercel)       │     │   (Railway)      │     │   (Supabase)    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                       │
         │                       ▼
         │              ┌──────────────────┐
         │              │  OpenAI APIs     │
         │              │  - Whisper       │
         │              │  - GPT-4         │
         │              └──────────────────┘
         │
         ▼
┌──────────────────┐
│  Google Drive    │
│  (Asset Storage) │
└──────────────────┘
```

---

## DATABASE SCHEMA

### Table: `projects`
```sql
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Input
    input_video_url TEXT NOT NULL,
    input_filename TEXT,
    content_type VARCHAR(50), -- 'testimonial', 'case_study', 'founder_story'
    
    -- Status
    status VARCHAR(50) DEFAULT 'pending', -- pending, processing, completed, failed
    processing_stage VARCHAR(100), -- current step name
    progress_percent INTEGER DEFAULT 0,
    
    -- Metadata
    user_id UUID,
    duration_seconds INTEGER,
    file_size_mb DECIMAL,
    
    -- Results
    transcript_id UUID REFERENCES transcripts(id),
    
    -- GHL Integration (Phase 2)
    ghl_location_id VARCHAR(255),
    ghl_pushed_at TIMESTAMP
);
```

### Table: `transcripts`
```sql
CREATE TABLE transcripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP DEFAULT NOW(),
    
    project_id UUID REFERENCES projects(id),
    
    -- Raw transcript
    full_text TEXT NOT NULL,
    language VARCHAR(10) DEFAULT 'en',
    
    -- Segments with timestamps
    segments JSONB, -- [{start: 0.0, end: 5.5, text: "..."}, ...]
    
    -- Speaker identification (if multi-person)
    speakers JSONB -- [{speaker: "Abby", segments: [...]}]
);
```

### Table: `moments`
```sql
CREATE TABLE moments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP DEFAULT NOW(),
    
    project_id UUID REFERENCES projects(id),
    transcript_id UUID REFERENCES transcripts(id),
    
    -- Moment identification
    moment_type VARCHAR(50), -- 'problem', 'solution', 'result', 'emotional_peak', 'cta'
    start_time DECIMAL NOT NULL, -- seconds
    end_time DECIMAL NOT NULL,
    duration DECIMAL GENERATED ALWAYS AS (end_time - start_time) STORED,
    
    -- Content
    transcript TEXT,
    summary TEXT,
    
    -- Scoring
    sentiment_score DECIMAL, -- -1 to 1
    importance_score DECIMAL, -- 0 to 1
    
    -- Quotes
    quotable_text TEXT,
    quotable_score DECIMAL
);
```

### Table: `assets`
```sql
CREATE TABLE assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP DEFAULT NOW(),
    
    project_id UUID REFERENCES projects(id),
    moment_id UUID REFERENCES moments(id),
    
    -- Asset type
    asset_type VARCHAR(50), -- 'video_clip', 'video_vertical', 'thumbnail', 'quote_card', 'email', 'social_post', 'blog_outline'
    
    -- Content
    title VARCHAR(255),
    description TEXT,
    content TEXT, -- For text assets (emails, posts, etc)
    
    -- File info (for video/image assets)
    file_url TEXT, -- Google Drive URL
    file_path TEXT, -- Internal path
    file_size_mb DECIMAL,
    duration_seconds INTEGER,
    dimensions VARCHAR(50), -- "1920x1080", "1080x1920", etc
    
    -- Metadata
    format VARCHAR(20), -- 'mp4', 'jpg', 'txt', etc
    status VARCHAR(50) DEFAULT 'pending', -- pending, processing, completed, failed
    
    -- GHL Integration (Phase 2)
    ghl_asset_id VARCHAR(255),
    ghl_uploaded_at TIMESTAMP
);
```

### Table: `users`
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMP DEFAULT NOW(),
    
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    
    -- GHL Integration (Phase 2)
    ghl_agency_id VARCHAR(255),
    ghl_access_token TEXT,
    ghl_refresh_token TEXT,
    ghl_token_expires_at TIMESTAMP
);
```

---

## API ENDPOINTS

### Projects

**POST /api/projects**
```json
{
  "input_video_url": "https://drive.google.com/...",
  "content_type": "testimonial"
}
```
Response: `{ "id": "uuid", "status": "pending" }`

**GET /api/projects/{id}**
Response:
```json
{
  "id": "uuid",
  "status": "processing",
  "processing_stage": "generating_video_clips",
  "progress_percent": 65,
  "transcript": { ... },
  "assets_count": 12
}
```

**GET /api/projects/{id}/assets**
Response:
```json
{
  "assets": [
    {
      "id": "uuid",
      "asset_type": "video_clip",
      "title": "Abby on her initial challenge",
      "duration_seconds": 15,
      "file_url": "https://drive.google.com/...",
      "download_url": "..."
    }
  ]
}
```

**POST /api/projects/{id}/download-all**
Response: `{ "zip_url": "https://storage.../project-uuid.zip" }`

### Processing

**POST /api/projects/{id}/process**
Starts processing pipeline.

**GET /api/projects/{id}/status**
Returns real-time processing status.

### GHL Integration (Phase 2)

**POST /api/ghl/connect**
Initiates OAuth flow.

**POST /api/projects/{id}/push-to-ghl**
Pushes all assets to connected GHL location.

---

## PROCESSING PIPELINE

### Stage 1: Ingest (5%)
1. Download video from URL
2. Validate file type (mp4, mov, avi)
3. Extract metadata (duration, size)
4. Create project record

### Stage 2: Transcribe (15%)
1. Extract audio track (FFmpeg)
2. Send to Whisper API
3. Parse response (text + segments)
4. Store transcript

### Stage 3: Analyze (35%)
1. Send transcript to GPT-4 for moment identification
2. Prompt: "Identify key moments: problem statements, solutions, results, emotional peaks"
3. Parse response, extract timestamps
4. Calculate sentiment/importance scores
5. Store moments

### Stage 4: Generate Video Assets (65%)
1. For each high-importance moment:
   - Extract 5s, 15s, 30s clips (FFmpeg)
   - Create vertical version (9:16 crop)
   - Generate captions (SRT → burn-in)
   - Upload to Google Drive
   - Store asset records

### Stage 5: Generate Text Assets (85%)
1. Generate quotable snippets (GPT-4)
2. Create email templates (3 variations)
3. Write social captions (Twitter/LinkedIn/Instagram)
4. Draft blog outline
5. Store all as text assets

### Stage 6: Finalize (100%)
1. Update project status to "completed"
2. Generate asset manifest
3. Create ZIP bundle
4. Send notification

---

## PROMPT TEMPLATES

### Moment Identification
```
Analyze this transcript and identify key moments in this {content_type}.

Transcript:
{transcript_text}

For each moment, provide:
1. Timestamp range (start - end)
2. Moment type: problem, solution, result, emotional_peak, or cta
3. Brief summary (1-2 sentences)
4. Sentiment score (-1 to 1)
5. Importance score (0 to 1)
6. Most quotable line from this moment

Return as JSON array.
```

### Email Generation
```
Create 3 email templates based on this testimonial moment.

Context: {moment_summary}
Quote: {quotable_text}

For each email:
1. Subject line (max 50 chars)
2. Preview text (max 100 chars)
3. Body (200-300 words)
4. Call to action

Make them suitable for a {industry} audience.
```

### Social Caption Generation
```
Create social media captions for this moment.

Quote: {quotable_text}
Context: {moment_summary}

Create:
1. Twitter/X version (max 280 chars)
2. LinkedIn version (professional tone, 100-150 words)
3. Instagram version (engaging, with hashtags)
4. Facebook version (community-focused)
```

---

## VIDEO PROCESSING SPECS

### Clip Extraction
```python
# 5-second micro-clip
ffmpeg -i input.mp4 -ss {start} -t 5 -vf "scale=1920:1080" -c:v libx264 -preset fast -crf 23 output_5s.mp4

# 15-second clip
ffmpeg -i input.mp4 -ss {start} -t 15 -vf "scale=1920:1080" -c:v libx264 -preset fast -crf 23 output_15s.mp4

# Vertical version (9:16)
ffmpeg -i input.mp4 -ss {start} -t 15 -vf "crop=1080:1920,scale=1080:1920" -c:v libx264 -preset fast -crf 23 output_vertical.mp4
```

### Caption Burn-in
```python
# Generate SRT from transcript segment
# Then burn in:
ffmpeg -i input.mp4 -vf "subtitles=captions.srt:force_style='FontSize=24,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2'" output.mp4
```

---

## FRONTEND WIREFRAMES

### 1. Upload Page
```
┌─────────────────────────────────────┐
│  Crucible Fission Reactor           │
│                                     │
│  ┌─────────────────────────────┐    │
│  │                             │    │
│  │   📹                        │    │
│  │                             │    │
│  │   Drop video here or click  │    │
│  │   to upload                 │    │
│  │                             │    │
│  └─────────────────────────────┘    │
│                                     │
│  Content Type: [Testimonial ▼]     │
│                                     │
│  [🚀 Fissionate]                    │
└─────────────────────────────────────┘
```

### 2. Processing Page
```
┌─────────────────────────────────────┐
│  Processing Your Content...         │
│                                     │
│  ████████████████░░░░  65%         │
│                                     │
│  Current: Generating video clips    │
│                                     │
│  [Cancel]                           │
└─────────────────────────────────────┘
```

### 3. Dashboard (Results)
```
┌─────────────────────────────────────┐
│  ✅ Processing Complete!            │
│  32 assets created from your video  │
│                                     │
│  [Download All] [Push to GHL]       │
│                                     │
│  ┌────────────────────────────────┐ │
│  │ VIDEO CLIPS (12)              │ │
│  │ [▶] [▶] [▶] [▶] [▶] [▶]     │ │
│  └────────────────────────────────┘ │
│                                     │
│  ┌────────────────────────────────┐ │
│  │ QUOTABLE SNIPPETS (10)        │ │
│  │ "The results were amazing..." │ │
│  │ "I highly recommend..."       │ │
│  └────────────────────────────────┘ │
│                                     │
│  ┌────────────────────────────────┐ │
│  │ EMAIL TEMPLATES (3)           │ │
│  │ Preview Subject Lines...      │ │
│  └────────────────────────────────┘ │
└─────────────────────────────────────┘
```

---

## ERROR HANDLING

### Retry Strategy
- Whisper API: 3 retries with exponential backoff
- GPT-4 API: 3 retries with exponential backoff
- Video processing: 2 retries
- Google Drive upload: 3 retries

### Fallbacks
- If transcription fails: Return error, allow re-upload
- If moment analysis fails: Use simple timestamp-based segmentation
- If video generation fails: Mark asset as failed, continue with others
- If GHL push fails: Store for manual retry

### User Notifications
- Email on completion
- Email on failure with error details
- Dashboard shows processing status
- Real-time progress updates (WebSockets - Phase 2)

---

## SECURITY CONSIDERATIONS

### Data Storage
- Videos stored temporarily during processing
- Deleted after 7 days (configurable)
- Transcripts and assets stored indefinitely
- Google Drive files remain in user's drive

### API Keys
- OpenAI key stored as environment variable
- Never logged or exposed to frontend
- Rotatable without code changes

### User Authentication (Phase 2)
- JWT tokens
- Session expiration (24 hours)
- Refresh token rotation

---

## SCALING CONSIDERATIONS

### Current (MVP)
- Single worker process
- Sequential processing
- Local file storage (temporary)

### Phase 2 Scaling
- Redis queue for job management
- Multiple worker processes
- Dedicated video processing servers
- CDN for asset delivery

### Phase 3 Enterprise
- Kubernetes orchestration
- Auto-scaling workers
- Multi-region deployment
- Dedicated GPU instances for video processing

---

## TESTING STRATEGY

### Unit Tests
- Transcript parsing
- Moment identification accuracy
- Video clip extraction
- File upload/download

### Integration Tests
- End-to-end Abby video processing
- API endpoint testing
- Google Drive integration

### Load Tests
- Concurrent upload handling
- Processing queue depth
- Memory usage during video processing

---

## DEPLOYMENT CHECKLIST

### Pre-launch
- [ ] All API keys configured
- [ ] Database migrations run
- [ ] Domain DNS configured
- [ ] SSL certificates active
- [ ] Error monitoring (Sentry) configured
- [ ] Analytics (Plausible/PostHog) configured

### Launch
- [ ] Deploy backend to Railway
- [ ] Deploy frontend to Vercel
- [ ] Configure domain
- [ ] Test Abby video end-to-end
- [ ] Create demo account

### Post-launch
- [ ] Monitor error rates
- [ ] Track processing times
- [ ] Collect user feedback
- [ ] Iterate on prompts

---

*Document Version: 0.1*  
*Last Updated: February 16, 2026*  
*Status: Ready for development*
