from sqlalchemy import create_engine, Column, String, DateTime, Integer, Text, ForeignKey, JSON, DECIMAL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

from app.config import get_settings

settings = get_settings()

# Database setup
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Project(Base):
    """Main project entity representing a video processing job."""
    __tablename__ = "projects"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Input
    input_video_url = Column(Text, nullable=True)
    input_filename = Column(String(255))
    content_type = Column(String(50), default="testimonial")  # testimonial, case_study, founder_story
    
    # Status
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    processing_stage = Column(String(100))
    progress_percent = Column(Integer, default=0)
    
    # Metadata
    user_id = Column(UUID(as_uuid=True))
    duration_seconds = Column(Integer)
    file_size_mb = Column(DECIMAL(10, 2))
    
    # Relationships
    transcript = relationship("Transcript", back_populates="project", uselist=False)
    moments = relationship("Moment", back_populates="project")
    assets = relationship("Asset", back_populates="project")
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "status": self.status,
            "processing_stage": self.processing_stage,
            "progress_percent": self.progress_percent,
            "content_type": self.content_type,
            "duration_seconds": self.duration_seconds,
            "file_size_mb": float(self.file_size_mb) if self.file_size_mb else None,
        }


class Transcript(Base):
    """Transcript of the video with segments."""
    __tablename__ = "transcripts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"))
    project = relationship("Project", back_populates="transcript")
    
    full_text = Column(Text, nullable=False)
    language = Column(String(10), default="en")
    segments = Column(JSON)  # [{"start": 0.0, "end": 5.5, "text": "..."}]
    speakers = Column(JSON)  # [{"speaker": "Abby", "segments": []}]


class Moment(Base):
    """Key moments identified in the transcript."""
    __tablename__ = "moments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"))
    project = relationship("Project", back_populates="moments")
    
    # Moment identification
    moment_type = Column(String(50))  # problem, solution, result, emotional_peak, cta
    start_time = Column(DECIMAL(10, 3), nullable=False)  # seconds
    end_time = Column(DECIMAL(10, 3), nullable=False)
    
    # Content
    transcript = Column(Text)
    summary = Column(Text)
    
    # Scoring
    sentiment_score = Column(DECIMAL(3, 2))  # -1 to 1
    importance_score = Column(DECIMAL(3, 2))  # 0 to 1
    
    # Quotes
    quotable_text = Column(Text)
    quotable_score = Column(DECIMAL(3, 2))


class Asset(Base):
    """Generated assets (videos, images, text)."""
    __tablename__ = "assets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"))
    project = relationship("Project", back_populates="assets")
    moment_id = Column(UUID(as_uuid=True), ForeignKey("moments.id"), nullable=True)
    
    # Asset type
    asset_type = Column(String(50))  # video_clip, video_vertical, thumbnail, quote_card, email, social_post, blog_outline
    
    # Content
    title = Column(String(255))
    description = Column(Text)
    content = Column(Text)  # For text assets
    
    # File info
    file_url = Column(Text)  # Google Drive URL
    file_path = Column(Text)  # Local path
    file_size_mb = Column(DECIMAL(10, 2))
    duration_seconds = Column(Integer)
    dimensions = Column(String(50))
    
    # Metadata
    format = Column(String(20))  # mp4, jpg, txt, etc
    status = Column(String(50), default="pending")  # pending, processing, completed, failed


def get_db():
    """Database session generator."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)
