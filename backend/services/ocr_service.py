"""
OCR Service using Tesseract

Handles optical character recognition for scanned documents and images.
"""
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
import subprocess
from PIL import Image
import numpy as np
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.exceptions import ProcessingError

logger = get_logger(__name__)


class OCRService:
    """Service for OCR processing."""
    
    def __init__(self):
        self.tesseract_cmd = settings.TESSERACT_CMD
        self.supported_languages = settings.tesseract_language_list
        self._check_tesseract_availability()
    
    def _check_tesseract_availability(self) -> bool:
        """Check if Tesseract is available."""
        try:
            result = subprocess.run(
                [self.tesseract_cmd, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                logger.info(f"Tesseract available: {version_line}")
                return True
            else:
                logger.warning("Tesseract command failed")
                return False
        except FileNotFoundError:
            logger.warning(f"Tesseract not found at: {self.tesseract_cmd}")
            return False
        except Exception as e:
            logger.warning(f"Tesseract check failed: {str(e)}")
            return False
    
    def is_available(self) -> bool:
        """Check if OCR is available."""
        return self._check_tesseract_availability()
    
    def preprocess_image(
        self,
        image: Image.Image,
        enhance_contrast: bool = True,
        denoise: bool = True,
    ) -> Image.Image:
        """
        Preprocess image for better OCR results.
        
        Args:
            image: PIL Image
            enhance_contrast: Whether to enhance contrast
            denoise: Whether to apply denoising
        
        Returns:
            Preprocessed PIL Image
        """
        try:
            # Convert to grayscale
            if image.mode != 'L':
                image = image.convert('L')
            
            # Convert to numpy array for processing
            img_array = np.array(image)
            
            # Enhance contrast using histogram equalization
            if enhance_contrast:
                from skimage import exposure
                img_array = exposure.equalize_adapthist(
                    img_array,
                    clip_limit=0.03
                ) * 255
                img_array = img_array.astype(np.uint8)
            
            # Denoise
            if denoise:
                from skimage.restoration import denoise_bilateral
                img_array = denoise_bilateral(
                    img_array,
                    sigma_color=0.05,
                    sigma_spatial=15,
                    channel_axis=None
                ) * 255
                img_array = img_array.astype(np.uint8)
            
            # Convert back to PIL Image
            processed_image = Image.fromarray(img_array)
            
            return processed_image
        
        except Exception as e:
            logger.warning(f"Image preprocessing failed: {str(e)}")
            # Return original image if preprocessing fails
            return image
    
    def extract_text_from_image(
        self,
        image_path: Path,
        language: str = "eng",
        preprocess: bool = True,
    ) -> Dict[str, Any]:
        """
        Extract text from image using Tesseract OCR.
        
        Args:
            image_path: Path to image file
            language: Tesseract language code (e.g., 'eng', 'hin')
            preprocess: Whether to preprocess image
        
        Returns:
            OCR result with text and metadata
        """
        start_time = datetime.utcnow()
        
        try:
            if not self.is_available():
                raise ProcessingError(
                    "Tesseract OCR not available",
                    details={"tesseract_cmd": self.tesseract_cmd}
                )
            
            logger.info(f"Performing OCR on image: {image_path.name}")
            
            # Load image
            image = Image.open(image_path)
            original_size = image.size
            
            # Preprocess if requested
            if preprocess:
                image = self.preprocess_image(image)
            
            # Save preprocessed image temporarily
            temp_path = image_path.parent / f"temp_ocr_{image_path.name}"
            image.save(temp_path)
            
            try:
                # Run Tesseract
                result = subprocess.run(
                    [
                        self.tesseract_cmd,
                        str(temp_path),
                        "stdout",
                        "-l", language,
                        "--psm", "3",  # Fully automatic page segmentation
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode == 0:
                    extracted_text = result.stdout.strip()
                    
                    ocr_result = {
                        "success": True,
                        "text": extracted_text,
                        "char_count": len(extracted_text),
                        "language": language,
                        "preprocessed": preprocess,
                        "original_size": original_size,
                        "processing_duration_seconds": (datetime.utcnow() - start_time).total_seconds(),
                    }
                    
                    # Estimate quality based on text length and characteristics
                    quality_score = self._estimate_ocr_quality(extracted_text)
                    ocr_result["quality_score"] = quality_score
                    
                    if extracted_text:
                        logger.info(f"OCR extracted {len(extracted_text)} characters")
                    else:
                        logger.warning("OCR completed but no text extracted")
                        ocr_result["warning"] = "No text extracted from image"
                    
                    return ocr_result
                else:
                    error_msg = result.stderr.strip()
                    logger.error(f"Tesseract failed: {error_msg}")
                    raise ProcessingError(
                        f"OCR failed: {error_msg}",
                        details={"language": language}
                    )
            
            finally:
                # Clean up temp file
                if temp_path.exists():
                    temp_path.unlink()
        
        except ProcessingError:
            raise
        except Exception as e:
            logger.error(f"OCR processing failed: {str(e)}", exc_info=True)
            raise ProcessingError(
                f"Failed to perform OCR: {str(e)}",
                details={"file": image_path.name, "language": language}
            )
    
    def _estimate_ocr_quality(self, text: str) -> str:
        """
        Estimate OCR quality based on text characteristics.
        
        Returns:
            Quality rating: "high", "medium", "low", or "unknown"
        """
        if not text:
            return "unknown"
        
        # Simple heuristics
        char_count = len(text)
        word_count = len(text.split())
        
        if char_count < 50:
            return "low"
        
        # Check for unusual character patterns
        unusual_chars = sum(1 for c in text if not c.isalnum() and not c.isspace() and c not in ".,!?;:-'\"()[]{}/@#$%&*")
        unusual_ratio = unusual_chars / max(char_count, 1)
        
        if unusual_ratio > 0.1:
            return "low"
        elif word_count > 50 and unusual_ratio < 0.05:
            return "high"
        else:
            return "medium"
    
    def pdf_to_images(self, pdf_path: Path) -> List[Path]:
        """
        Convert PDF pages to images for OCR.
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            List of image file paths
        """
        try:
            from pdf2image import convert_from_path
            
            logger.info(f"Converting PDF to images: {pdf_path.name}")
            
            # Convert PDF to images
            images = convert_from_path(pdf_path, dpi=300)
            
            image_paths = []
            output_dir = pdf_path.parent / "pdf_images"
            output_dir.mkdir(exist_ok=True)
            
            for i, image in enumerate(images, 1):
                image_path = output_dir / f"{pdf_path.stem}_page_{i}.png"
                image.save(image_path, "PNG")
                image_paths.append(image_path)
                logger.info(f"Saved page {i} as image: {image_path.name}")
            
            return image_paths
        
        except ImportError:
            logger.error("pdf2image not available")
            raise ProcessingError(
                "pdf2image library required for PDF-to-image conversion",
                details={"install": "pip install pdf2image"}
            )
        except Exception as e:
            logger.error(f"PDF to image conversion failed: {str(e)}", exc_info=True)
            raise ProcessingError(
                f"Failed to convert PDF to images: {str(e)}",
                details={"file": pdf_path.name}
            )
    
    def process_scanned_pdf(
        self,
        pdf_path: Path,
        language: str = "eng",
    ) -> Dict[str, Any]:
        """
        Process scanned PDF by converting to images and performing OCR.
        
        Args:
            pdf_path: Path to scanned PDF
            language: OCR language
        
        Returns:
            Combined OCR result from all pages
        """
        start_time = datetime.utcnow()
        
        try:
            # Convert PDF to images
            image_paths = self.pdf_to_images(pdf_path)
            
            # Perform OCR on each page
            page_results = []
            all_text = []
            
            for page_num, image_path in enumerate(image_paths, 1):
                try:
                    ocr_result = self.extract_text_from_image(image_path, language)
                    page_results.append({
                        "page_number": page_num,
                        "text": ocr_result["text"],
                        "char_count": ocr_result["char_count"],
                        "quality_score": ocr_result.get("quality_score", "unknown"),
                    })
                    all_text.append(ocr_result["text"])
                except Exception as e:
                    logger.warning(f"OCR failed for page {page_num}: {str(e)}")
                    page_results.append({
                        "page_number": page_num,
                        "text": "",
                        "char_count": 0,
                        "error": str(e),
                    })
            
            # Combine all text
            combined_text = "\n\n".join(all_text)
            
            result = {
                "success": bool(combined_text.strip()),
                "text": combined_text,
                "num_pages": len(image_paths),
                "pages": page_results,
                "total_chars": len(combined_text),
                "extraction_method": "tesseract_ocr",
                "language": language,
                "processing_duration_seconds": (datetime.utcnow() - start_time).total_seconds(),
            }
            
            # Clean up image files
            for image_path in image_paths:
                try:
                    image_path.unlink()
                except:
                    pass
            
            try:
                image_paths[0].parent.rmdir()
            except:
                pass
            
            logger.info(f"Scanned PDF OCR completed: {len(combined_text)} total characters")
            return result
        
        except Exception as e:
            logger.error(f"Scanned PDF processing failed: {str(e)}", exc_info=True)
            raise ProcessingError(
                f"Failed to process scanned PDF: {str(e)}",
                details={"file": pdf_path.name}
            )
