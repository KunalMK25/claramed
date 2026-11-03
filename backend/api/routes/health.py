"""
Health Check Endpoints

Provides health and readiness checks for the application.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from typing import Dict, Any

from backend.database.connection import get_db
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.services.radiology_service import RadiologyService
from backend.services.ocr_service import OCRService

logger = get_logger(__name__)

router = APIRouter()


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Basic health check endpoint.
    
    Returns application status without checking external dependencies.
    """
    return {
        "status": "healthy",
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/health/ready", status_code=status.HTTP_200_OK)
async def readiness_check(db: Session = Depends(get_db)):
    """
    Readiness check endpoint.
    
    Checks if the application and its dependencies are ready to handle requests.
    """
    checks: Dict[str, Any] = {
        "status": "ready",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {},
    }
    
    # Check database connectivity
    try:
        db.execute(text("SELECT 1"))
        checks["checks"]["database"] = {
            "status": "healthy",
            "message": "Database connection OK",
        }
    except Exception as e:
        checks["status"] = "not_ready"
        checks["checks"]["database"] = {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}",
        }
        logger.error("Database health check failed", error=str(e))
    
    # Check OCR availability (non-critical)
    try:
        ocr_service = OCRService()
        ocr_available = ocr_service.is_available()
        checks["checks"]["ocr"] = {
            "status": "available" if ocr_available else "unavailable",
            "message": "Tesseract OCR " + ("available" if ocr_available else "not installed"),
            "critical": False,
        }
    except Exception as e:
        checks["checks"]["ocr"] = {
            "status": "unavailable",
            "message": f"OCR check failed: {str(e)}",
            "critical": False,
        }
    
    # Check radiology model availability (non-critical)
    try:
        radiology_service = RadiologyService()
        model_available = radiology_service.is_available()
        checks["checks"]["radiology_ai"] = {
            "status": "available" if model_available else "unavailable",
            "message": "TorchXRayVision " + ("model loaded" if model_available else "not available"),
            "critical": False,
        }
    except Exception as e:
        checks["checks"]["radiology_ai"] = {
            "status": "unavailable",
            "message": f"Radiology AI check failed: {str(e)}",
            "critical": False,
        }
    
    # Check LLM configuration (non-critical)
    if settings.GROQ_API_KEY and settings.GROQ_API_KEY != "your_groq_api_key_here":
        checks["checks"]["llm"] = {
            "status": "configured",
            "message": "LLM provider configured",
            "critical": False,
        }
    else:
        checks["checks"]["llm"] = {
            "status": "not_configured",
            "message": "LLM API key not configured",
            "critical": False,
        }
    
    # Determine overall status
    critical_checks = [
        check for check in checks["checks"].values()
        if check.get("critical", True) and check["status"] in ["unhealthy", "unavailable"]
    ]
    
    if critical_checks:
        checks["status"] = "not_ready"
        return checks, status.HTTP_503_SERVICE_UNAVAILABLE
    
    return checks
