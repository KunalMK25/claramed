"""
Analysis Result Model
"""
import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, JSON, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.database.connection import Base


class ResultType(str, enum.Enum):
    """Result type enumeration."""
    EXPLANATION = "explanation"
    WELLNESS_TIPS = "wellness_tips"
    STRUCTURED_FINDINGS = "structured_findings"
    RADIOLOGY_INFERENCE = "radiology_inference"
    EMERGENCY_CLASSIFICATION = "emergency_classification"


class AnalysisResult(Base):
    """Analysis result record."""
    
    __tablename__ = "analysis_results"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("medical_analyses.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Result data
    result_type = Column(Enum(ResultType), nullable=False, index=True)
    content = Column(JSON, nullable=False)
    
    # Model metadata
    model_name = Column(String(100), nullable=True)
    model_version = Column(String(50), nullable=True)
    provider = Column(String(50), nullable=True)
    
    # Processing metadata
    tokens_used = Column(Integer, nullable=True)
    processing_duration_seconds = Column(String(20), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    analysis = relationship("MedicalAnalysis", back_populates="results")
    
    def __repr__(self):
        return f"<AnalysisResult(id={self.id}, type={self.result_type})>"
