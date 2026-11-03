"""
Radiology AI Service using TorchXRayVision

Handles chest X-ray analysis using pretrained deep learning models.
"""
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
import torch
import torchvision.transforms as transforms
from PIL import Image
import numpy as np
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.exceptions import ModelError, ProcessingError, ValidationError

logger = get_logger(__name__)


class RadiologyService:
    """Service for radiology AI inference."""
    
    def __init__(self):
        self.model_name = settings.RADIOLOGY_MODEL_NAME
        self.device = settings.RADIOLOGY_DEVICE
        self.model = None
        self.model_loaded = False
        self.supported_labels = []
    
    def load_model(self) -> bool:
        """
        Load TorchXRayVision model.
        
        Returns:
            True if model loaded successfully
        """
        if self.model_loaded:
            logger.info(f"Model already loaded: {self.model_name}")
            return True
        
        try:
            import torchxrayvision as xrv
            
            logger.info(f"Loading TorchXRayVision model: {self.model_name}")
            logger.info(f"Device: {self.device}")
            
            # Load the model based on configuration
            if self.model_name == "densenet121-res224-all":
                self.model = xrv.models.DenseNet(weights="densenet121-res224-all")
            elif self.model_name == "resnet50-res512-all":
                self.model = xrv.models.ResNet(weights="resnet50-res512-all")
            else:
                # Try generic loading
                self.model = xrv.models.DenseNet(weights=self.model_name)
            
            # Move model to device
            self.model = self.model.to(self.device)
            self.model.eval()
            
            # Get supported labels from the model
            if hasattr(self.model, 'pathologies'):
                self.supported_labels = self.model.pathologies
                logger.info(f"Model supports {len(self.supported_labels)} pathologies:")
                logger.info(f"Labels: {', '.join(self.supported_labels)}")
            else:
                logger.warning("Model does not expose pathology labels")
                # Default labels for densenet121-res224-all
                self.supported_labels = [
                    "Atelectasis", "Consolidation", "Infiltration", "Pneumothorax",
                    "Edema", "Emphysema", "Fibrosis", "Effusion", "Pneumonia",
                    "Pleural_Thickening", "Cardiomegaly", "Nodule", "Mass", "Hernia"
                ]
            
            self.model_loaded = True
            logger.info(f"Model loaded successfully: {self.model_name}")
            return True
        
        except ImportError as e:
            logger.error(f"TorchXRayVision not available: {str(e)}")
            raise ModelError(
                "TorchXRayVision not installed or import failed",
                model_name=self.model_name,
                details={"error": str(e)}
            )
        except Exception as e:
            logger.error(f"Model loading failed: {str(e)}", exc_info=True)
            raise ModelError(
                f"Failed to load radiology model: {str(e)}",
                model_name=self.model_name
            )
    
    def is_available(self) -> bool:
        """Check if radiology AI is available."""
        try:
            return self.load_model()
        except:
            return False
    
    def validate_image(self, image_path: Path) -> None:
        """Validate chest X-ray image."""
        if not image_path.exists():
            raise ValidationError(f"Image file not found: {image_path}")
        
        # Check file extension
        valid_extensions = [".png", ".jpg", ".jpeg", ".dcm"]
        if image_path.suffix.lower() not in valid_extensions:
            raise ValidationError(
                f"Invalid image format: {image_path.suffix}",
                details={"supported": valid_extensions}
            )
        
        # Check file size
        file_size_mb = image_path.stat().st_size / (1024 * 1024)
        if file_size_mb > settings.MAX_UPLOAD_SIZE_MB:
            raise ValidationError(
                f"Image too large: {file_size_mb:.2f}MB (max: {settings.MAX_UPLOAD_SIZE_MB}MB)"
            )
        
        # Try to open and validate image
        try:
            image = Image.open(image_path)
            width, height = image.size
            
            if width > settings.MAX_IMAGE_DIMENSION or height > settings.MAX_IMAGE_DIMENSION:
                raise ValidationError(
                    f"Image dimensions too large: {width}x{height} (max: {settings.MAX_IMAGE_DIMENSION})"
                )
            
            logger.info(f"Image validated: {width}x{height}, {file_size_mb:.2f}MB")
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f"Invalid image file: {str(e)}")
    
    def preprocess_image(self, image_path: Path) -> torch.Tensor:
        """
        Preprocess image for model inference.
        
        Args:
            image_path: Path to chest X-ray image
        
        Returns:
            Preprocessed tensor ready for model
        """
        try:
            # Load image
            image = Image.open(image_path)
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Convert to numpy array
            img_array = np.array(image)
            
            # Convert to grayscale (chest X-rays are grayscale)
            if len(img_array.shape) == 3:
                # Simple averaging for RGB to grayscale
                img_array = np.mean(img_array, axis=2)
            
            # Normalize to [0, 1]
            img_array = img_array.astype(np.float32) / 255.0
            
            # Resize to model input size (224x224 for densenet121-res224)
            # TorchXRayVision expects specific size
            target_size = 224 if "224" in self.model_name else 512
            
            img_pil = Image.fromarray((img_array * 255).astype(np.uint8))
            img_pil = img_pil.resize((target_size, target_size), Image.BILINEAR)
            img_array = np.array(img_pil) / 255.0
            
            # Normalize using TorchXRayVision's expected normalization
            # These models expect zero-centered data
            img_array = (img_array - 0.5) / 0.5
            
            # Convert to tensor: [1, 1, H, W]
            img_tensor = torch.from_numpy(img_array).float()
            img_tensor = img_tensor.unsqueeze(0).unsqueeze(0)
            
            logger.info(f"Image preprocessed: shape {img_tensor.shape}")
            return img_tensor
        
        except Exception as e:
            logger.error(f"Image preprocessing failed: {str(e)}", exc_info=True)
            raise ProcessingError(
                f"Failed to preprocess image: {str(e)}",
                details={"file": image_path.name}
            )
    
    def analyze_chest_xray(self, image_path: Path) -> Dict[str, Any]:
        """
        Analyze chest X-ray image.
        
        Args:
            image_path: Path to chest X-ray image
        
        Returns:
            Analysis result with findings
        """
        start_time = datetime.utcnow()
        
        try:
            # Ensure model is loaded
            if not self.load_model():
                raise ModelError(
                    "Radiology model not available",
                    model_name=self.model_name
                )
            
            # Validate image
            self.validate_image(image_path)
            
            logger.info(f"Analyzing chest X-ray: {image_path.name}")
            
            # Preprocess image
            img_tensor = self.preprocess_image(image_path)
            
            # Move to device
            img_tensor = img_tensor.to(self.device)
            
            # Run inference
            with torch.no_grad():
                outputs = self.model(img_tensor)
            
            # Convert outputs to numpy
            scores = outputs.cpu().numpy()[0]
            
            # Create findings list
            findings = []
            for label, score in zip(self.supported_labels, scores):
                findings.append({
                    "label": label,
                    "model_score": float(score),
                })
            
            # Sort by score (descending)
            findings.sort(key=lambda x: x["model_score"], reverse=True)
            
            result = {
                "success": True,
                "modality": "chest_xray",
                "model_name": self.model_name,
                "model_version": "pretrained",
                "device": self.device,
                "findings": findings,
                "num_findings": len(findings),
                "processing_duration_seconds": (datetime.utcnow() - start_time).total_seconds(),
                "disclaimer": "This is AI-generated model output, not a radiologist's diagnosis. Professional medical interpretation is required.",
            }
            
            logger.info(f"Chest X-ray analysis completed: {len(findings)} findings")
            
            # Log top findings
            top_findings = findings[:5]
            for finding in top_findings:
                logger.info(f"  {finding['label']}: {finding['model_score']:.3f}")
            
            return result
        
        except (ModelError, ValidationError, ProcessingError):
            raise
        except Exception as e:
            logger.error(f"Chest X-ray analysis failed: {str(e)}", exc_info=True)
            raise ProcessingError(
                f"Failed to analyze chest X-ray: {str(e)}",
                details={"file": image_path.name}
            )
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get radiology model information."""
        return {
            "model_name": self.model_name,
            "model_loaded": self.model_loaded,
            "device": self.device,
            "supported_labels": self.supported_labels,
            "num_labels": len(self.supported_labels),
        }
