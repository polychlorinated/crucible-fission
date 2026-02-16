from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "postgresql://postgres:password@localhost:5432/fission"
    
    # Moonshot/Kimi API
    moonshot_api_key: str = ""
    moonshot_base_url: str = "https://api.moonshot.cn/v1"
    
    # Google Drive
    google_credentials_path: str = "/app/google-credentials.json"
    
    # Storage
    temp_dir: str = "/tmp/fission"
    max_file_size_mb: int = 500
    
    # Processing
    whisper_model: str = "base"  # tiny, base, small
    max_workers: int = 2
    
    # App
    debug: bool = False
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
