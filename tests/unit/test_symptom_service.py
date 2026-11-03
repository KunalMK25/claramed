"""
Unit Tests for Symptom Service
"""
import pytest
from backend.services.symptom_service import SymptomService
from backend.core.exceptions import ValidationError


class TestSymptomService:
    """Test symptom analysis service."""
    
    def test_validate_symptoms_empty(self):
        """Test validation rejects empty symptoms."""
        service = SymptomService()
        
        with pytest.raises(ValidationError):
            service.validate_symptoms("", "English")
    
    def test_validate_symptoms_too_long(self):
        """Test validation rejects too-long symptoms."""
        service = SymptomService()
        long_symptoms = "x" * 6000
        
        with pytest.raises(ValidationError):
            service.validate_symptoms(long_symptoms, "English")
    
    def test_validate_symptoms_unsupported_language(self):
        """Test validation rejects unsupported language."""
        service = SymptomService()
        
        with pytest.raises(ValidationError):
            service.validate_symptoms("headache", "Klingon")
    
    def test_validate_symptoms_valid(self):
        """Test validation accepts valid input."""
        service = SymptomService()
        
        # Should not raise
        service.validate_symptoms("I have a headache", "English")
