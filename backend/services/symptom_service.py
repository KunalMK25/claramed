"""
Symptom Analysis Service

Handles symptom explanation, emergency classification, and wellness guidance.
"""
from typing import Dict, Any, Optional
from datetime import datetime
from backend.ai.llm_provider import get_llm_provider
from backend.ai.prompts import (
    SYMPTOM_EXPLANATION_PROMPT,
    WELLNESS_TIPS_PROMPT,
)
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.exceptions import ProcessingError, ValidationError

logger = get_logger(__name__)


class SymptomService:
    """Service for symptom analysis and explanation."""
    
    def __init__(self):
        self.llm_provider = get_llm_provider()
    
    def validate_symptoms(self, symptoms: str, language: str) -> None:
        """Validate symptom input."""
        if not symptoms or not symptoms.strip():
            raise ValidationError("Symptoms description cannot be empty")
        
        if len(symptoms) > 5000:
            raise ValidationError("Symptoms description too long (max 5000 characters)")
        
        if language not in settings.SUPPORTED_LANGUAGES:
            raise ValidationError(
                f"Unsupported language: {language}",
                details={"supported": settings.SUPPORTED_LANGUAGES}
            )
    
    def analyze_symptoms(
        self,
        symptoms: str,
        language: str = "English",
        include_wellness: bool = True,
    ) -> Dict[str, Any]:
        """
        Analyze symptoms and generate explanation.
        
        Args:
            symptoms: User's symptom description
            language: Response language
            include_wellness: Whether to include wellness tips
        
        Returns:
            Analysis result dictionary
        """
        start_time = datetime.utcnow()
        
        try:
            # Validate input
            self.validate_symptoms(symptoms, language)
            
            logger.info(
                "Analyzing symptoms",
                symptom_length=len(symptoms),
                language=language
            )
            
            # Generate explanation
            explanation_chain = self.llm_provider.create_chain(SYMPTOM_EXPLANATION_PROMPT)
            explanation = explanation_chain.invoke({
                "symptoms": symptoms,
                "language": language
            })
            
            result = {
                "explanation": explanation.strip(),
                "language": language,
                "model": self.llm_provider.model,
                "processing_duration_seconds": (datetime.utcnow() - start_time).total_seconds(),
            }
            
            # Generate wellness tips if requested
            if include_wellness:
                wellness_tips = self._generate_wellness_tips(symptoms, language)
                result["wellness_tips"] = wellness_tips
            
            logger.info("Symptom analysis completed successfully")
            return result
        
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Symptom analysis failed: {str(e)}", exc_info=True)
            raise ProcessingError(
                f"Failed to analyze symptoms: {str(e)}",
                details={"language": language}
            )
    
    def _generate_wellness_tips(self, symptoms: str, language: str) -> str:
        """Generate wellness and lifestyle tips."""
        try:
            wellness_chain = self.llm_provider.create_chain(WELLNESS_TIPS_PROMPT)
            wellness_tips = wellness_chain.invoke({
                "symptoms": symptoms,
                "language": language
            })
            return wellness_tips.strip()
        
        except Exception as e:
            logger.warning(f"Wellness tips generation failed: {str(e)}")
            # Return empty string if wellness tips fail (non-critical)
            return ""
