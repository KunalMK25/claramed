"""
Audit Event Model
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from backend.database.connection import Base


class AuditEvent(Base):
    """Audit event record."""
    
    __tablename__ = "audit_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Request information
    request_id = Column(String(100), nullable=False, index=True)
    requesting_client_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    requesting_client_name = Column(String(100), nullable=True)
    
    # Action details
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False, index=True)
    resource_id = Column(String(100), nullable=True, index=True)
    
    # Outcome
    outcome = Column(String(20), nullable=False, index=True)  # success, failure, denied
    error_message = Column(String(500), nullable=True)
    
    # Additional context (renamed from 'metadata' to avoid SQLAlchemy reserved name)
    event_metadata = Column(JSON, nullable=True)
    
    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self):
        return f"<AuditEvent(id={self.id}, action={self.action}, outcome={self.outcome})>"
