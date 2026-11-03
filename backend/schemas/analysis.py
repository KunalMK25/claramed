"""
Analysis API Schemas
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
from backend.models.analysis import AnalysisType, AnalysisStatus


# Request Schemas

class SymptomAnalysisRequest(BaseModel):
    """Request schema for symptom analysis."""
    symptoms: str = Field(..., min_length=1, max_length=5000, description="Symptom description")
    language: str = Field(default="English", description="Response language")
    include_wellness: bool = Field(default=True, description="Include wellness tips")
    external_patient_reference: Optional[str] = Field(None, description="External patient ID")
    external_hospital_reference: Optional[str] = Field(None, description="External hospital ID")
    
    @validator("symptoms")
    def validate_symptoms(cls, v):
        if not v.strip():
            raise ValueError("Symptoms cannot be empty")
        return v.strip()


class DocumentAnalysisRequest(BaseModel):
    """Request schema for document analysis."""
    language: str = Field(default="English", description="Response language")
    external_patient_reference: Optional[str] = Field(None, description="External patient ID")
    external_hospital_reference: Optional[str] = Field(None, description="External hospital ID")


# Response Schemas

class EmergencyClassification(BaseModel):
    """Emergency classification result."""
    emergency_flagged: bool
    message: Optional[str] = None
    confidence: Optional[str] = None


class SymptomAnalysisResponse(BaseModel):
    """Response schema for symptom analysis."""
    analysis_id: str
    status: AnalysisStatus
    analysis_type: AnalysisType
    language: str
    emergency_classification: Optional[EmergencyClassification] = None
    explanation: Optional[str] = None
    wellness_tips: Optional[str] = None
    created_at: datetime
    processing_duration_seconds: Optional[float] = None


class RadiologyFinding(BaseModel):
    """Radiology finding."""
    label: str
    model_score: float


class RadiologyAnalysisResponse(BaseModel):
    """Response schema for radiology analysis."""
    analysis_id: str
    status: AnalysisStatus
    modality: str
    model_name: str
    findings: List[RadiologyFinding]
    explanation: Optional[str] = None
    created_at: datetime
    disclaimer: str


class AnalysisStatusResponse(BaseModel):
    """Response schema for analysis status."""
    analysis_id: str
    status: AnalysisStatus
    analysis_type: AnalysisType
    created_at: datetime
    updated_at: datetime
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class AnalysisListResponse(BaseModel):
    """Response schema for analysis list."""
    analyses: List[AnalysisStatusResponse]
    total: int
    page: int
    page_size: int


class AnalysisResultResponse(BaseModel):
    """Response schema for analysis results."""
    analysis_id: str
    status: AnalysisStatus
    analysis_type: AnalysisType
    language: str
    results: Dict[str, Any]
    created_at: datetime
    completed_at: Optional[datetime] = None
