"""
Integration Client Model
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from backend.database.connection import Base


class IntegrationClient(Base):
    """Integration client for API access."""
    
    __tablename__ = "integration_clients"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Client information
    client_name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(String(500), nullable=True)
    
    # Authentication
    hashed_api_key = Column(String(255), nullable=False, unique=True)
    
    # Authorization
    scopes = Column(ARRAY(String), default=list, nullable=False)
    allowed_hospitals = Column(ARRAY(String), default=list, nullable=True)
    
    # Status
    active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Rate limiting
    rate_limit_per_minute = Column(String(10), nullable=True)
    rate_limit_per_hour = Column(String(10), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<IntegrationClient(id={self.id}, name={self.client_name}, active={self.active})>"
