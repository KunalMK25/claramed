"""
Medical Analysis Model
"""
import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Enum, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.database.connection import Base


class AnalysisType(str, enum.Enum):
    """Analysis type enumeration."""
    SYMPTOM = "symptom"
    REPORT_PDF = "report_pdf"
    XRAY = "xray"
    DOCUMENT = "document"


class AnalysisStatus(str, enum.Enum):
    """Analysis status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class MedicalAnalysis(Base):
    """Medical analysis record."""
    
    __tablename__ = "medical_analyses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_type = Column(Enum(AnalysisType), nullable=False, index=True)
    status = Column(Enum(AnalysisStatus), default=AnalysisStatus.PENDING, nullable=False, index=True)
    
    # Input data
    input_text = Column(Text, nullable=True)
    input_data = Column(JSON, nullable=True)
    language = Column(String(20), default="English", nullable=False)
    
    # External references (for JeevaCare integration)
    external_patient_reference = Column(String(255), nullable=True, index=True)
    external_hospital_reference = Column(String(255), nullable=True, index=True)
    external_system = Column(String(50), nullable=True)
    
    # Request metadata
    requesting_client_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    request_id = Column(String(100), nullable=True, index=True)
    
    # Emergency classification
    emergency_flagged = Column(Boolean, default=False, nullable=False)
    emergency_message = Column(Text, nullable=True)
    
    # Processing metadata
    processing_started_at = Column(DateTime, nullable=True)
    processing_completed_at = Column(DateTime, nullable=True)
    processing_duration_seconds = Column(String(20), nullable=True)
    
    # Error information
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    results = relationship("AnalysisResult", back_populates="analysis", cascade="all, delete-orphan")
    documents = relationship("UploadedDocument", back_populates="analysis", cascade="all, delete-orphan")
    findings = relationship("RadiologyFinding", back_populates="analysis", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<MedicalAnalysis(id={self.id}, type={self.analysis_type}, status={self.status})>"
