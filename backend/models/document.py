"""
Uploaded Document Model
"""
import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.database.connection import Base


class DocumentType(str, enum.Enum):
    """Document type enumeration."""
    PDF = "pdf"
    IMAGE_PNG = "image_png"
    IMAGE_JPEG = "image_jpeg"
    IMAGE_JPG = "image_jpg"
    DICOM = "dicom"


class UploadedDocument(Base):
    """Uploaded document record."""
    
    __tablename__ = "uploaded_documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("medical_analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # File metadata
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(Enum(DocumentType), nullable=False)
    file_size = Column(Integer, nullable=False)
    checksum = Column(String(64), nullable=False)
    
    # Storage information
    storage_key = Column(String(500), nullable=False, unique=True)
    storage_provider = Column(String(50), nullable=False)
    
    # Processing metadata
    extracted_text = Column(String, nullable=True)
    ocr_performed = Column(String(10), default="no", nullable=False)
    ocr_quality_score = Column(String(20), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    analysis = relationship("MedicalAnalysis", back_populates="documents")
    
    def __repr__(self):
        return f"<UploadedDocument(id={self.id}, filename={self.filename})>"
