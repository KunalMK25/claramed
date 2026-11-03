"""
Emergency Classification Service

Conservative emergency warning system based on symptom keywords and LLM analysis.
"""
from typing import Dict, Any, List, Optional
from backend.ai.llm_provider import get_llm_provider
from backend.ai.prompts import EMERGENCY_CLASSIFICATION_PROMPT
from backend.core.logging import get_logger

logger = get_logger(__name__)


# Emergency keyword patterns (conservative - many false positives acceptable)
EMERGENCY_KEYWORDS = {
    "en": [
        "chest pain", "severe chest", "crushing chest",
        "difficulty breathing", "can't breathe", "cannot breathe", "trouble breathing",
        "severe bleeding", "heavy bleeding", "bleeding heavily",
        "unconscious", "loss of consciousness", "passed out",
        "stroke", "facial drooping", "slurred speech", "arm weakness",
        "severe headache", "worst headache",
        "suicide", "suicidal", "kill myself",
        "overdose", "poisoning",
        "severe burn", "major burn",
        "choking",
        "seizure",
        "severe allergic reaction", "anaphylaxis",
        "severe abdominal pain",
    ],
}


class EmergencyService:
    """Service for emergency classification."""
    
    def __init__(self):
        self.llm_provider = get_llm_provider(temperature=0.0, max_tokens=10)
    
    def classify_emergency(
        self,
        symptoms: str,
        language: str = "English",
        use_llm: bool = True,
    ) -> Dict[str, Any]:
        """
        Classify whether symptoms indicate a potential emergency.
        
        This is a CONSERVATIVE classifier - false positives are acceptable
        to err on the side of patient safety.
        
        Args:
            symptoms: User's symptom description
            language: Response language
            use_llm: Whether to use LLM classification (in addition to keywords)
        
        Returns:
            Emergency classification result
        """
        try:
            symptoms_lower = symptoms.lower()
            
            # First: Check keyword-based detection (fast and reliable)
            keyword_match = self._check_emergency_keywords(symptoms_lower)
            
            # Second: LLM-based classification if enabled and no keyword match
            llm_classified = False
            llm_result = None
            
            if use_llm and not keyword_match:
                llm_result = self._llm_classify(symptoms, language)
                llm_classified = llm_result
            
            # Conservative: Flag as emergency if EITHER method detects it
            is_emergency = keyword_match or llm_classified
            
            result = {
                "emergency_flagged": is_emergency,
                "keyword_match": keyword_match,
                "llm_classified": llm_classified,
                "language": language,
            }
            
            if is_emergency:
                result["message"] = self._get_emergency_message(language)
                logger.warning(
                    "Emergency flagged",
                    keyword_match=keyword_match,
                    llm_classified=llm_classified
                )
            else:
                logger.info("No emergency detected")
            
            return result
        
        except Exception as e:
            logger.error(f"Emergency classification failed: {str(e)}", exc_info=True)
            # On error, default to showing emergency warning (fail-safe)
            return {
                "emergency_flagged": True,
                "keyword_match": False,
                "llm_classified": False,
                "language": language,
                "message": self._get_emergency_message(language),
                "error": "Classification failed - showing emergency warning as precaution",
            }
    
    def _check_emergency_keywords(self, symptoms_lower: str) -> bool:
        """Check for emergency keywords."""
        # Currently only English keywords implemented
        keywords = EMERGENCY_KEYWORDS.get("en", [])
        
        for keyword in keywords:
            if keyword in symptoms_lower:
                logger.info(f"Emergency keyword matched: {keyword}")
                return True
        
        return False
    
    def _llm_classify(self, symptoms: str, language: str) -> bool:
        """Use LLM to classify emergency status."""
        try:
            classification_chain = self.llm_provider.create_chain(
                EMERGENCY_CLASSIFICATION_PROMPT
            )
            response = classification_chain.invoke({
                "symptoms": symptoms,
                "language": language
            })
            
            response_upper = response.strip().upper()
            
            # Check for "YES" in multiple languages
            yes_indicators = ["YES", "हाँ", "ಹೌದು", "ஆம்", "అవును", "SÍ", "SI", "OUI"]
            
            is_emergency = any(indicator in response_upper for indicator in yes_indicators)
            
            logger.info(f"LLM emergency classification: {response} -> {is_emergency}")
            return is_emergency
        
        except Exception as e:
            logger.warning(f"LLM classification failed: {str(e)}")
            # On LLM failure, return False (keyword check already happened)
            return False
    
    def _get_emergency_message(self, language: str) -> str:
        """Get localized emergency warning message."""
        messages = {
            "English": "🚨 This may be a medical emergency! Please call emergency services or visit the nearest hospital immediately.",
            "Hindi": "🚨 यह एक चिकित्सा आपातकाल हो सकता है! कृपया तुरंत आपातकालीन सेवाओं को कॉल करें या निकटतम अस्पताल जाएं।",
            "Kannada": "🚨 ಇದು ವೈದ್ಯಕೀಯ ತುರ್ತು ಪರಿಸ್ಥಿತಿ ಇರಬಹುದು! ದಯವಿಟ್ಟು ತಕ್ಷಣ ತುರ್ತು ಸೇವೆಗಳಿಗೆ ಕರೆ ಮಾಡಿ ಅಥವಾ ಹತ್ತಿರದ ಆಸ್ಪತ್ರೆಗೆ ಭೇಟಿ ನೀಡಿ।",
            "Tamil": "🚨 இது ஒரு மருத்துவ அவசர நிலையாக இருக்கலாம்! தயவுசெய்து உடனடியாக அவசர சேவைகளை அழைக்கவும் அல்லது அருகிலுள்ள மருத்துவமனைக்குச் செல்லவும்।",
            "Telugu": "🚨 ఇది వైద్య అత్యవసర పరిస్థితి కావచ్చు! దయచేసి వెంటనే అత్యవసర సేవలకు కాల్ చేయండి లేదా సమీప ఆసుపత్రిని సందర్శించండి।",
            "Spanish": "🚨 ¡Esto puede ser una emergencia médica! Por favor, llame a los servicios de emergencia o visite el hospital más cercano de inmediato.",
            "French": "🚨 Cela peut être une urgence médicale! Veuillez appeler les services d'urgence ou vous rendre immédiatement à l'hôpital le plus proche.",
        }
        
        return messages.get(language, messages["English"])
