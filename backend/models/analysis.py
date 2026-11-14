"""
Medical Analysis Model
"""
import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Enum, Text, JSON, Integer, UniqueConstraint
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


class DeliveryStatus:
    """Values of MedicalAnalysis.delivery_status (a plain string column)."""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"      # callback retries exhausted; results are still pollable
    SKIPPED = "skipped"    # client has no webhook or was deactivated


class RecordKind:
    """Values of MedicalAnalysis.external_record_kind (a plain string column)."""
    RADIOLOGY = "radiology"
    DOCUMENT = "document"


class MedicalAnalysis(Base):
    """Medical analysis record."""
    
    __tablename__ = "medical_analyses"
    __table_args__ = (
        UniqueConstraint(
            "requesting_client_id", "external_record_kind", "external_record_id",
            name="uq_analysis_client_record",
        ),
    )

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

    # Integration: client-supplied record (idempotency) and callback state
    external_record_id = Column(String(255), nullable=True)
    external_record_kind = Column(String(20), nullable=True)  # see RecordKind
    delivery_status = Column(String(20), nullable=True)  # see DeliveryStatus
    delivery_attempts = Column(Integer, default=0, nullable=False, server_default="0")
    delivery_last_error = Column(String(500), nullable=True)
    callback_delivered_at = Column(DateTime, nullable=True)
    results_expire_at = Column(DateTime, nullable=True, index=True)

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
