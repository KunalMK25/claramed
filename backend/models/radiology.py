"""
Radiology Finding Model
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.database.connection import Base


class RadiologyFinding(Base):
    """Radiology AI finding record."""
    
    __tablename__ = "radiology_findings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("medical_analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Finding data
    finding_label = Column(String(100), nullable=False, index=True)
    model_score = Column(Float, nullable=False)
    
    # Model metadata
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(50), nullable=True)
    modality = Column(String(50), default="chest_xray", nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    analysis = relationship("MedicalAnalysis", back_populates="findings")
    
    def __repr__(self):
        return f"<RadiologyFinding(id={self.id}, label={self.finding_label}, score={self.model_score})>"
