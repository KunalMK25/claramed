"""
ClaraMed Security and Authentication
"""
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from .config import settings
from .exceptions import AuthenticationError, AuthorizationError


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_api_key() -> str:
    """Generate a secure random API key."""
    return f"sk_claramed_{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    """Hash an API key for secure storage."""
    salt = settings.API_KEY_HASH_SECRET
    return hashlib.sha256(f"{api_key}{salt}".encode()).hexdigest()


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """Verify an API key against its hash."""
    return hmac.compare_digest(hash_api_key(plain_key), hashed_key)


def hash_password(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT access token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError as e:
        raise AuthenticationError(f"Invalid token: {str(e)}")


def validate_scopes(required_scopes: list[str], user_scopes: list[str]) -> bool:
    """Validate that user has required scopes."""
    return all(scope in user_scopes for scope in required_scopes)
