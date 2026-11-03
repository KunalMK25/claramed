"""
Unit Tests for Emergency Service
"""
import pytest
from backend.services.emergency_service import EmergencyService


class TestEmergencyService:
    """Test emergency classification service."""
    
    def test_emergency_keywords_chest_pain(self):
        """Test emergency keyword detection for chest pain."""
        service = EmergencyService()
        
        result = service.classify_emergency(
            symptoms="I have severe chest pain",
            language="English",
            use_llm=False  # Test keyword only
        )
        
        assert result["emergency_flagged"] is True
        assert result["keyword_match"] is True
    
    def test_emergency_keywords_breathing(self):
        """Test emergency keyword detection for breathing issues."""
        service = EmergencyService()
        
        result = service.classify_emergency(
            symptoms="I can't breathe properly",
            language="English",
            use_llm=False
        )
        
        assert result["emergency_flagged"] is True
        assert result["keyword_match"] is True
    
    def test_no_emergency_simple_headache(self):
        """Test non-emergency classification."""
        service = EmergencyService()
        
        result = service.classify_emergency(
            symptoms="I have a mild headache",
            language="English",
            use_llm=False
        )
        
        assert result["emergency_flagged"] is False
        assert result["keyword_match"] is False
    
    def test_emergency_message_localization(self):
        """Test emergency message is localized."""
        service = EmergencyService()
        
        # English
        result_en = service.classify_emergency(
            symptoms="severe chest pain",
            language="English",
            use_llm=False
        )
        assert "emergency" in result_en["message"].lower()
        
        # Hindi  
        result_hi = service.classify_emergency(
            symptoms="severe chest pain",
            language="Hindi",
            use_llm=False
        )
        assert result_hi["message"] != result_en["message"]
