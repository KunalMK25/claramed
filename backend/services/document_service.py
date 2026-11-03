"""
Document Processing Service

Handles PDF text extraction, document validation, and structured information extraction.
"""
from typing import Dict, Any, Optional, List
from pathlib import Path
import hashlib
from datetime import datetime
import PyPDF2
from backend.ai.llm_provider import get_llm_provider
from backend.ai.prompts import REPORT_EXPLAINER_PROMPT, STRUCTURED_FINDINGS_PROMPT
from backend.core.logging import get_logger
from backend.core.exceptions import ProcessingError, ValidationError

logger = get_logger(__name__)


class DocumentService:
    """Service for document processing."""
    
    def __init__(self):
        self.llm_provider = get_llm_provider()
    
    def validate_pdf(self, file_path: Path, max_size_mb: int = 10) -> None:
        """Validate PDF file."""
        if not file_path.exists():
            raise ValidationError(f"File not found: {file_path}")
        
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > max_size_mb:
            raise ValidationError(
                f"File too large: {file_size_mb:.2f}MB (max: {max_size_mb}MB)"
            )
        
        if file_path.suffix.lower() != ".pdf":
            raise ValidationError(
                f"Invalid file type: {file_path.suffix} (expected .pdf)"
            )
    
    def extract_text_from_pdf(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract text from PDF using PyPDF2.
        
        Args:
            file_path: Path to PDF file
        
        Returns:
            Extraction result with text and metadata
        """
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Extracting text from PDF: {file_path.name}")
            
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                
                num_pages = len(reader.pages)
                extracted_text = []
                page_texts = []
                
                for page_num, page in enumerate(reader.pages, 1):
                    try:
                        text = page.extract_text()
                        if text:
                            extracted_text.append(text)
                            page_texts.append({
                                "page_number": page_num,
                                "text": text.strip(),
                                "char_count": len(text)
                            })
                    except Exception as e:
                        logger.warning(f"Failed to extract page {page_num}: {str(e)}")
                        page_texts.append({
                            "page_number": page_num,
                            "text": "",
                            "char_count": 0,
                            "error": str(e)
                        })
                
                full_text = "\n\n".join(extracted_text)
                
                result = {
                    "success": bool(full_text.strip()),
                    "text": full_text,
                    "num_pages": num_pages,
                    "pages": page_texts,
                    "total_chars": len(full_text),
                    "extraction_method": "pypdf2",
                    "processing_duration_seconds": (datetime.utcnow() - start_time).total_seconds(),
                }
                
                if not full_text.strip():
                    logger.warning("No text extracted - PDF may be scanned/image-based")
                    result["requires_ocr"] = True
                else:
                    logger.info(f"Extracted {len(full_text)} characters from {num_pages} pages")
                    result["requires_ocr"] = False
                
                return result
        
        except PyPDF2.errors.PdfReadError as e:
            logger.error(f"PDF read error: {str(e)}")
            raise ProcessingError(
                f"Invalid or corrupted PDF: {str(e)}",
                details={"file": file_path.name}
            )
        except Exception as e:
            logger.error(f"PDF extraction failed: {str(e)}", exc_info=True)
            raise ProcessingError(
                f"Failed to extract text from PDF: {str(e)}",
                details={"file": file_path.name}
            )
    
    def explain_report(
        self,
        report_text: str,
        language: str = "English",
    ) -> Dict[str, Any]:
        """
        Generate plain-language explanation of medical report.
        
        Args:
            report_text: Extracted report text
            language: Response language
        
        Returns:
            Explanation result
        """
        start_time = datetime.utcnow()
        
        try:
            if not report_text or not report_text.strip():
                raise ValidationError("Report text is empty")
            
            if len(report_text) > 50000:
                logger.warning("Report text very long, truncating for LLM")
                report_text = report_text[:50000] + "\n\n[... text truncated ...]"
            
            logger.info(f"Generating report explanation ({len(report_text)} chars)")
            
            explanation_chain = self.llm_provider.create_chain(REPORT_EXPLAINER_PROMPT)
            explanation = explanation_chain.invoke({
                "report_text": report_text,
                "language": language
            })
            
            result = {
                "explanation": explanation.strip(),
                "language": language,
                "model": self.llm_provider.model,
                "input_length": len(report_text),
                "processing_duration_seconds": (datetime.utcnow() - start_time).total_seconds(),
            }
            
            logger.info("Report explanation generated successfully")
            return result
        
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Report explanation failed: {str(e)}", exc_info=True)
            raise ProcessingError(
                f"Failed to generate report explanation: {str(e)}",
                details={"language": language}
            )
    
    def extract_structured_findings(
        self,
        report_text: str,
        language: str = "English",
    ) -> Optional[str]:
        """
        Extract structured findings from report text using LLM.
        
        This is a best-effort extraction and may not always succeed.
        
        Args:
            report_text: Extracted report text
            language: Response language
        
        Returns:
            Structured findings or None if extraction fails
        """
        try:
            if not report_text or len(report_text) < 50:
                return None
            
            logger.info("Extracting structured findings")
            
            findings_chain = self.llm_provider.create_chain(STRUCTURED_FINDINGS_PROMPT)
            findings = findings_chain.invoke({
                "report_text": report_text[:10000],  # Limit for structured extraction
                "language": language
            })
            
            return findings.strip() if findings else None
        
        except Exception as e:
            logger.warning(f"Structured extraction failed: {str(e)}")
            return None
    
    def calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of file."""
        sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        
        return sha256.hexdigest()
