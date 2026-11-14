"""
ClaraMed Configuration Management
"""
from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import os


PRODUCTION = "production"
# Placeholder secrets shipped in .env.example / the defaults below; never acceptable in production.
DEFAULT_API_KEY_HASH_SECRET = "change_this_to_a_secure_random_string"
DEFAULT_SECRET_KEY = "change_this_to_a_secure_random_string_for_jwt"


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
    GROQ_VISION_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"  # non-chest X-rays
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
    # Set true when the API and the Celery worker are known to mount the same storage volume
    STORAGE_SHARED_CONFIRMED: bool = False
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
    API_KEY_HASH_SECRET: str = DEFAULT_API_KEY_HASH_SECRET
    SECRET_KEY: str = DEFAULT_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Integration
    CLARAMED_INTEGRATION_ENABLED: bool = True
    CALLBACK_MAX_ATTEMPTS: int = 5
    CALLBACK_BACKOFF_BASE_SECONDS: int = 120  # 120+240+480+960 = 30 min between 5 attempts
    CALLBACK_TIMEOUT_SECONDS: int = 10
    RESULT_RETENTION_DAYS: int = 30
    STALE_JOB_SECONDS: int = 1800
    # Deprecated, unused: per-client webhook settings now live on IntegrationClient
    JEEVACARE_WEBHOOK_SECRET: Optional[str] = None
    JEEVACARE_CALLBACK_URL: Optional[str] = None
    
    # Supported Languages
    SUPPORTED_LANGUAGES: str = "English,Hindi,Kannada,Tamil,Telugu,Spanish,French"
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 10
    RATE_LIMIT_PER_HOUR: int = 100
    
    @validator("DATABASE_URL")
    def pin_psycopg2_driver(cls, v):
        # SQLAlchemy may default to psycopg3 for plain postgresql:// URLs;
        # this project depends on psycopg2.
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+psycopg2://", 1)
        return v

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
        
        if self.API_KEY_HASH_SECRET == DEFAULT_API_KEY_HASH_SECRET:
            missing.append("API_KEY_HASH_SECRET (use a secure random string)")
        
        if self.SECRET_KEY == DEFAULT_SECRET_KEY:
            missing.append("SECRET_KEY (use a secure random string)")
        
        return missing


# Global settings instance
def storage_topology_warning(app_env: str, provider: str, shared_volume_confirmed: bool = False) -> str | None:
    """Warn when local storage is used in production: the API and the worker must see the same files."""
    if app_env == PRODUCTION and provider == "local" and not shared_volume_confirmed:
        return ("STORAGE_PROVIDER=local in production: the API and the Celery worker must share the same "
                "volume, or use STORAGE_PROVIDER=s3. Files written by the API are otherwise invisible to the worker. "
                "Set STORAGE_SHARED_CONFIRMED=true once they do.")
    return None


_DEFAULT_SECRETS = {DEFAULT_API_KEY_HASH_SECRET, DEFAULT_SECRET_KEY}
MIN_SECRET_LENGTH = 32


def production_config_errors(app_env: str, debug: bool, api_key_hash_secret: str, secret_key: str) -> list[str]:
    """Reasons the app must refuse to start in production. Empty list = fine."""
    if app_env != PRODUCTION:
        return []
    errors = []
    if debug:
        errors.append("DEBUG must be false in production (it enables CORS '*' and SQL logging)")
    for name, value in (("API_KEY_HASH_SECRET", api_key_hash_secret), ("SECRET_KEY", secret_key)):
        if value in _DEFAULT_SECRETS or len(value) < MIN_SECRET_LENGTH:
            errors.append(f"{name} must be set to a random value of at least {MIN_SECRET_LENGTH} characters")
    return errors


settings = Settings()


def get_settings() -> Settings:
    """Get settings instance for dependency injection."""
    return settings
