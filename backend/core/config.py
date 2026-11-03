"""
ClaraMed Configuration Management
"""
from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import os


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application
    APP_ENV: str = "development"
    APP_NAME: str = "ClaraMed"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    
    # Database
    DATABASE_URL: str = "postgresql://claramed:claramed@localhost:5432/claramed"
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Groq AI
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.1-8b-instant"
    GROQ_TEMPERATURE: float = 0.2
    GROQ_MAX_TOKENS: int = 1024
    
    # Tesseract OCR
    TESSERACT_CMD: str = "tesseract"
    TESSERACT_LANGUAGES: str = "eng"
    
    # Radiology AI
    RADIOLOGY_MODEL_NAME: str = "densenet121-res224-all"
    RADIOLOGY_DEVICE: str = "cpu"
    RADIOLOGY_MODEL_CACHE_DIR: str = "./models/cache"
    RADIOLOGY_BATCH_SIZE: int = 1
    
    # File Storage
    STORAGE_PROVIDER: str = "local"
    STORAGE_LOCAL_PATH: str = "./storage"
    STORAGE_BUCKET: str = "claramed-uploads"
    STORAGE_ENDPOINT: Optional[str] = None
    STORAGE_REGION: str = "us-east-1"
    STORAGE_ACCESS_KEY: Optional[str] = None
    STORAGE_SECRET_KEY: Optional[str] = None
    
    # Upload Limits
    MAX_UPLOAD_SIZE_MB: int = 10
    ANALYSIS_TIMEOUT_SECONDS: int = 120
    MAX_IMAGE_DIMENSION: int = 4096
    
    # Security
    API_KEY_HASH_SECRET: str = "change_this_to_a_secure_random_string"
    SECRET_KEY: str = "change_this_to_a_secure_random_string_for_jwt"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Integration
    JEEVACARE_WEBHOOK_SECRET: Optional[str] = None
    JEEVACARE_CALLBACK_URL: Optional[str] = None
    
    # Supported Languages
    SUPPORTED_LANGUAGES: str = "English,Hindi,Kannada,Tamil,Telugu,Spanish,French"
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 10
    RATE_LIMIT_PER_HOUR: int = 100
    
    @validator("SUPPORTED_LANGUAGES")
    def parse_languages(cls, v):
        if isinstance(v, str):
            return [lang.strip() for lang in v.split(",")]
        return v
    
    @property
    def max_upload_size_bytes(self) -> int:
        """Convert MB to bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    
    @property
    def tesseract_language_list(self) -> List[str]:
        """Parse tesseract languages."""
        return [lang.strip() for lang in self.TESSERACT_LANGUAGES.split(",")]
    
    def validate_required_settings(self) -> List[str]:
        """Validate required settings and return list of missing ones."""
        missing = []
        
        if not self.GROQ_API_KEY or self.GROQ_API_KEY == "your_groq_api_key_here":
            missing.append("GROQ_API_KEY")
        
        if self.API_KEY_HASH_SECRET == "change_this_to_a_secure_random_string":
            missing.append("API_KEY_HASH_SECRET (use a secure random string)")
        
        if self.SECRET_KEY == "change_this_to_a_secure_random_string_for_jwt":
            missing.append("SECRET_KEY (use a secure random string)")
        
        return missing


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get settings instance for dependency injection."""
    return settings
