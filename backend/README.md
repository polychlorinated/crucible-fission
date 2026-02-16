# Crucible Fission Reactor - Backend

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables (see PROJECT_CONFIG.md)

3. Run development server:
```bash
uvicorn app.main:app --reload
```

## Deployment (Railway)

1. Connect GitHub repo to Railway
2. Set environment variables in Railway dashboard
3. Deploy automatically on push

## API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
