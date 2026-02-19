FROM python:3.11-slim

WORKDIR /app

# Install system dependencies with full codec support
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libavfilter-dev \
    libswscale-dev \
    libswresample-dev \
    libx264-dev \
    libx265-dev \
    libvpx-dev \
    libmp3lame-dev \
    libopus-dev \
    libvorbis-dev \
    pkg-config \
    libffi-dev \
    libssl-dev \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements from backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download Whisper model during build
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')"

# Copy application from backend
COPY backend/app/ ./app/

# Expose port (Railway provides PORT env var)
EXPOSE 8000

# Copy and use entrypoint script
COPY start.sh .
RUN chmod +x start.sh

ENV PYTHONUNBUFFERED=1
CMD ["./start.sh"]
