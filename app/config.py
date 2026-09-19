"""Application Configuration Settings."""
import os
from dataclasses import dataclass

@dataclass
class Settings:
    PROJECT_NAME: str = "Real-Time Attendance Management System"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./attendance.db")
    SYNC_DATABASE_URL: str = os.getenv("SYNC_DATABASE_URL", "sqlite:///./attendance.db")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "realtime-attendance-super-secret-jwt-key-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # Attendance Engine Defaults
    DEFAULT_GRACE_PERIOD_MINUTES: int = 10
    DEFAULT_CONFIDENCE_THRESHOLD: float = 0.65
    DEFAULT_LAPLACIAN_THRESHOLD: float = 60.0
    MIN_FACE_SIZE: int = 70
    
    # Institution Info
    INSTITUTION_NAME: str = "Apex Institute of Technology"
    INSTITUTION_CODE: str = "AIT-EDU"

settings = Settings()
