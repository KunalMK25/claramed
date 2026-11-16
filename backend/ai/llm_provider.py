"""
LLM Provider Abstraction

Provides a clean interface for LLM interactions with multiple provider support.
"""
from typing import Optional, Dict, Any
from backend.ai.groq_fallback import TEXT_MODELS, build_llm, model_order
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from backend.core.config import settings
from backend.core.exceptions import ModelError
from backend.core.logging import get_logger

logger = get_logger(__name__)


class LLMProvider:
    """LLM provider abstraction."""
    
    def __init__(
        self,
        provider: str = "groq",
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        self.provider = provider
        self.model = model or settings.GROQ_MODEL
        self.temperature = temperature if temperature is not None else settings.GROQ_TEMPERATURE
        self.max_tokens = max_tokens or settings.GROQ_MAX_TOKENS
        
        self._llm = None
        self._initialize_llm()
    
    def _initialize_llm(self):
        """Initialize the LLM based on provider."""
        try:
            if self.provider == "groq":
                if not settings.GROQ_API_KEY:
                    raise ModelError(
                        "GROQ_API_KEY not configured",
                        model_name=self.model
                    )
                
                self._llm = build_llm(
                    model_order(self.model, TEXT_MODELS),
                    self.temperature,
                    self.max_tokens,
                    settings.GROQ_API_KEY,
                )
                logger.info(f"Initialized Groq LLM: {self.model}")
            
            else:
                raise ModelError(
                    f"Unsupported provider: {self.provider}",
                    model_name=self.model
                )
        
        except Exception as e:
            logger.error(f"LLM initialization failed: {str(e)}")
            raise ModelError(
                f"Failed to initialize LLM: {str(e)}",
                model_name=self.model,
                details={"provider": self.provider}
            )
    
    def create_chain(self, prompt_template: ChatPromptTemplate):
        """Create a LangChain chain with the LLM."""
        return prompt_template | self._llm | StrOutputParser()
    
    def invoke(self, prompt: str, variables: Optional[Dict[str, Any]] = None) -> str:
        """Invoke the LLM with a prompt."""
        try:
            if variables:
                response = self._llm.invoke(prompt.format(**variables))
            else:
                response = self._llm.invoke(prompt)
            
            # Extract content from response
            if hasattr(response, 'content'):
                return response.content
            return str(response)
        
        except Exception as e:
            logger.error(f"LLM invocation failed: {str(e)}")
            raise ModelError(
                f"LLM generation failed: {str(e)}",
                model_name=self.model
            )


def get_llm_provider(
    provider: str = "groq",
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> LLMProvider:
    """Get an LLM provider instance."""
    return LLMProvider(
        provider=provider,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
