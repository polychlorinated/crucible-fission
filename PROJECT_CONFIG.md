# Crucible Fission Reactor
## Project Configuration

---

## INFRASTRUCTURE (Provided by Andrew)

### GitHub
- **Repo:** https://github.com/polychlorinated/crucible-fission
- **Status:** Connected to Vercel and Railway

### Vercel
- **Account:** ames@polychlorinated.com
- **Status:** Ready for frontend deployment

### Railway
- **Status:** Connected to GitHub repo
- **Backend hosting:** Ready

### Supabase
- **Project URL:** https://jsilikclzwclfdksvovg.supabase.co
- **Region:** East US (North Virginia) us-east-1
- **Database Password:** m2_9qn7F_UG.Q!N
- **Connection String:** postgresql://postgres:m2_9qn7F_UG.Q!N@db.jsilikclzwclfdksvovg.supabase.co:5432/postgres

---

## ENVIRONMENT VARIABLES

### Backend (.env)
```
# Database
DATABASE_URL=postgresql://postgres:m2_9qn7F_UG.Q!N@db.jsilikclzwclfdksvovg.supabase.co:5432/postgres

# Kimi/Moonshot API
MOONSHOT_API_KEY=[TO BE ADDED]
MOONSHOT_BASE_URL=https://api.moonshot.cn/v1

# Google Drive (using existing credentials)
GOOGLE_CREDENTIALS_PATH=/path/to/google-credentials.json

# Storage
TEMP_DIR=/tmp/fission
MAX_FILE_SIZE_MB=500

# Processing
WHISPER_MODEL=base
MAX_WORKERS=2
```

### Frontend (.env.local)
```
NEXT_PUBLIC_API_URL=http://localhost:8000
# Production: https://api.fission.crucibleos.com
```

---

## KIMI API ACCESS

**For Production:**
- Direct Moonshot API calls from backend
- Base URL: https://api.moonshot.cn/v1
- Need API key from your account

**Documentation:** https://platform.moonshot.cn/docs

---

## PROJECT STRUCTURE

```
crucible-fission/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI entry
│   │   ├── config.py            # Settings
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── project.py       # Database models
│   │   │   └── asset.py
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── projects.py      # Project CRUD
│   │   │   ├── upload.py        # File upload
│   │   │   └── processing.py    # Status/checks
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── transcription.py # Whisper
│   │   │   ├── analysis.py      # Kimi/GPT
│   │   │   ├── video.py         # FFmpeg
│   │   │   └── storage.py       # Google Drive
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── helpers.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── Procfile                 # Railway
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx             # Upload page
│   │   ├── dashboard/
│   │   │   └── page.tsx         # Results dashboard
│   │   └── api/
│   ├── components/
│   │   ├── UploadDropzone.tsx
│   │   ├── ProcessingStatus.tsx
│   │   ├── AssetGallery.tsx
│   │   └── VideoPreview.tsx
│   ├── lib/
│   │   └── api.ts
│   ├── package.json
│   └── next.config.js
└── docs/
    └── README.md
```

---

## BUILD PHASES

### Phase 1: Backend Core (Days 1-3)
- [ ] FastAPI scaffolding
- [ ] Database models + migrations
- [ ] Upload endpoint
- [ ] Whisper integration (transcription)

### Phase 2: Processing Pipeline (Days 4-6)
- [ ] Kimi integration (moment identification)
- [ ] Video clip extraction (FFmpeg)
- [ ] Text asset generation
- [ ] Google Drive upload

### Phase 3: Frontend (Days 7-8)
- [ ] React + Tailwind setup
- [ ] Upload interface
- [ ] Processing status page
- [ ] Asset dashboard

### Phase 4: Integration (Days 9-10)
- [ ] End-to-end testing
- [ ] Abby video test
- [ ] Bug fixes
- [ ] Documentation

---

## IMMEDIATE NEXT STEPS

1. **Add Moonshot API key** to environment variables
2. **Start backend scaffolding** (I begin now)
3. **Test Supabase connection**
4. **Verify Railway deployment pipeline**

---

## QUESTIONS FOR ANDREW

1. **Moonshot API Key:** Can you add to Railway environment variables?
2. **Google Drive:** Use existing credentials file path?
3. **Collaboration:** Should I push code directly, or write locally for you to review?

---

*Ready to start coding.*
