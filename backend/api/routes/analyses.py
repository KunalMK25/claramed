"""
Medical Analysis API Routes

Handles symptom analysis, document processing, and radiology inference.
"""
from fastapi import APIRouter, Depends, Form, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
import tempfile
from pathlib import Path

from backend.database.connection import get_db
from backend.api.dependencies import require_authentication, check_analysis_access
from backend.models.analysis import MedicalAnalysis, AnalysisStatus, AnalysisType
from backend.models.result import AnalysisResult, ResultType
from backend.models.document import UploadedDocument, DocumentType
from backend.models.integration_client import IntegrationClient
from backend.schemas.analysis import (
    SymptomAnalysisRequest,
    SymptomAnalysisResponse,
    AnalysisStatusResponse,
    AnalysisListResponse,
    AnalysisResultResponse,
    EmergencyClassification,
)
from backend.services.symptom_service import SymptomService
from backend.services.emergency_service import EmergencyService
from backend.services.document_service import DocumentService
from backend.services.ocr_service import OCRService
from backend.services.radiology_report import BODY_PARTS, build_report, save_report
from backend.services.image_loader import SUPPORTED_EXTENSIONS
from backend.services.storage_service import StorageService
from backend.core.logging import get_logger
from backend.core.exceptions import ValidationError, ProcessingError
from datetime import datetime

logger = get_logger(__name__)

router = APIRouter()

# Upload extension -> stored document type (PDF/DICOM have no image-specific type)
DOCUMENT_TYPES = {
    ".png": DocumentType.IMAGE_PNG,
    ".jpg": DocumentType.IMAGE_JPEG,
    ".jpeg": DocumentType.IMAGE_JPEG,
    ".pdf": DocumentType.PDF,
    ".dcm": DocumentType.DICOM,
}


@router.post("/analyses", response_model=SymptomAnalysisResponse, status_code=status.HTTP_201_CREATED)
async def create_symptom_analysis(
    request: SymptomAnalysisRequest,
    db: Session = Depends(get_db),
    client: IntegrationClient = Depends(require_authentication),
):
    """
    Create a new symptom analysis.
    
    Analyzes user-provided symptoms, performs emergency classification,
    and generates educational explanations with wellness guidance.
    """
    try:
        logger.info(f"Creating symptom analysis", symptom_length=len(request.symptoms))
        
        # Create analysis record
        analysis = MedicalAnalysis(
            analysis_type=AnalysisType.SYMPTOM,
            status=AnalysisStatus.PROCESSING,
            input_text=request.symptoms,
            language=request.language,
            external_patient_reference=request.external_patient_reference,
            external_hospital_reference=request.external_hospital_reference,
            requesting_client_id=client.id if client else None,
            processing_started_at=datetime.utcnow(),
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        
        # Perform emergency classification
        emergency_service = EmergencyService()
        emergency_result = emergency_service.classify_emergency(
            symptoms=request.symptoms,
            language=request.language,
        )
        
        analysis.emergency_flagged = emergency_result["emergency_flagged"]
        analysis.emergency_message = emergency_result.get("message")
        
        # Save emergency classification result
        emergency_analysis_result = AnalysisResult(
            analysis_id=analysis.id,
            result_type=ResultType.EMERGENCY_CLASSIFICATION,
            content=emergency_result,
        )
        db.add(emergency_analysis_result)
        
        # Perform symptom analysis
        symptom_service = SymptomService()
        symptom_result = symptom_service.analyze_symptoms(
            symptoms=request.symptoms,
            language=request.language,
            include_wellness=request.include_wellness,
        )
        
        # Save explanation result
        explanation_result = AnalysisResult(
            analysis_id=analysis.id,
            result_type=ResultType.EXPLANATION,
            content={"explanation": symptom_result["explanation"]},
            model_name=symptom_result["model"],
        )
        db.add(explanation_result)
        
        # Save wellness tips if included
        if request.include_wellness and symptom_result.get("wellness_tips"):
            wellness_result = AnalysisResult(
                analysis_id=analysis.id,
                result_type=ResultType.WELLNESS_TIPS,
                content={"wellness_tips": symptom_result["wellness_tips"]},
            )
            db.add(wellness_result)
        
        # Update analysis status
        analysis.status = AnalysisStatus.COMPLETED
        analysis.processing_completed_at = datetime.utcnow()
        analysis.processing_duration_seconds = str(symptom_result["processing_duration_seconds"])
        
        db.commit()
        db.refresh(analysis)
        
        logger.info(f"Symptom analysis completed: {analysis.id}")
        
        # Build response
        return SymptomAnalysisResponse(
            analysis_id=str(analysis.id),
            status=analysis.status,
            analysis_type=analysis.analysis_type,
            language=analysis.language,
            emergency_classification=EmergencyClassification(
                emergency_flagged=emergency_result["emergency_flagged"],
                message=emergency_result.get("message"),
            ),
            explanation=symptom_result["explanation"],
            wellness_tips=symptom_result.get("wellness_tips"),
            created_at=analysis.created_at,
            processing_duration_seconds=symptom_result["processing_duration_seconds"],
        )
    
    except ValidationError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ProcessingError as e:
        db.rollback()
        if analysis:
            analysis.status = AnalysisStatus.FAILED
            analysis.error_message = str(e)
            db.commit()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"Symptom analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analysis failed"
        )


@router.get("/analyses/{analysis_id}", response_model=AnalysisStatusResponse)
async def get_analysis_status(
    analysis_id: str,
    db: Session = Depends(get_db),
    client: IntegrationClient = Depends(require_authentication),
):
    """
    Get analysis status by ID.
    
    Returns current processing status and metadata.
    """
    try:
        analysis_uuid = UUID(analysis_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid analysis ID format"
        )
    
    analysis = db.query(MedicalAnalysis).filter(
        MedicalAnalysis.id == analysis_uuid
    ).first()
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found"
        )
    
    # Check access if client is authenticated
    if client and not check_analysis_access(db, client, analysis_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return AnalysisStatusResponse(
        analysis_id=str(analysis.id),
        status=analysis.status,
        analysis_type=analysis.analysis_type,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at,
        processing_started_at=analysis.processing_started_at,
        processing_completed_at=analysis.processing_completed_at,
        error_message=analysis.error_message,
    )


@router.get("/analyses/{analysis_id}/results", response_model=AnalysisResultResponse)
async def get_analysis_results(
    analysis_id: str,
    db: Session = Depends(get_db),
    client: IntegrationClient = Depends(require_authentication),
):
    """
    Get complete analysis results.
    
    Returns all results including explanations, findings, and metadata.
    """
    try:
        analysis_uuid = UUID(analysis_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid analysis ID format"
        )
    
    analysis = db.query(MedicalAnalysis).filter(
        MedicalAnalysis.id == analysis_uuid
    ).first()
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found"
        )
    
    # Check access
    if client and not check_analysis_access(db, client, analysis_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Check if analysis is complete
    if analysis.status != AnalysisStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Analysis not completed yet (status: {analysis.status})"
        )
    
    # Gather all results
    results = {}
    
    for result in analysis.results:
        results[result.result_type.value] = result.content
    
    # Add findings for radiology
    if analysis.analysis_type == AnalysisType.XRAY and analysis.findings:
        results["findings"] = [
            {
                "label": finding.finding_label,
                "model_score": finding.model_score,
            }
            for finding in analysis.findings
        ]
    
    return AnalysisResultResponse(
        analysis_id=str(analysis.id),
        status=analysis.status,
        analysis_type=analysis.analysis_type,
        language=analysis.language,
        results=results,
        created_at=analysis.created_at,
        completed_at=analysis.processing_completed_at,
    )


@router.get("/analyses", response_model=AnalysisListResponse)
async def list_analyses(
    page: int = 1,
    page_size: int = 20,
    analysis_type: Optional[AnalysisType] = None,
    db: Session = Depends(get_db),
    client: IntegrationClient = Depends(require_authentication),
):
    """
    List analyses with pagination.
    
    Returns paginated list of analyses accessible by the client.
    """
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page must be >= 1"
        )
    
    if page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page size must be between 1 and 100"
        )
    
    query = db.query(MedicalAnalysis)
    
    # Filter by client if authenticated
    if client:
        query = query.filter(MedicalAnalysis.requesting_client_id == client.id)
    
    # Filter by type if specified
    if analysis_type:
        query = query.filter(MedicalAnalysis.analysis_type == analysis_type)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * page_size
    analyses = query.order_by(
        MedicalAnalysis.created_at.desc()
    ).offset(offset).limit(page_size).all()
    
    # Build response
    analysis_list = [
        AnalysisStatusResponse(
            analysis_id=str(a.id),
            status=a.status,
            analysis_type=a.analysis_type,
            created_at=a.created_at,
            updated_at=a.updated_at,
            processing_started_at=a.processing_started_at,
            processing_completed_at=a.processing_completed_at,
            error_message=a.error_message,
        )
        for a in analyses
    ]
    
    return AnalysisListResponse(
        analyses=analysis_list,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/analyses/{analysis_id}/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    analysis_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    client: IntegrationClient = Depends(require_authentication),
):
    """
    Upload a medical document for analysis.
    
    Supports PDF files. Performs text extraction and OCR if necessary.
    """
    try:
        analysis_uuid = UUID(analysis_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid analysis ID format"
        )
    
    analysis = db.query(MedicalAnalysis).filter(
        MedicalAnalysis.id == analysis_uuid
    ).first()
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found"
        )
    
    # Check access
    if client and not check_analysis_access(db, client, analysis_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files supported"
        )
    
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = Path(tmp_file.name)
        
        # Initialize services
        document_service = DocumentService()
        ocr_service = OCRService()
        storage_service = StorageService()
        
        # Validate PDF
        document_service.validate_pdf(tmp_path)
        
        # Calculate checksum
        checksum = document_service.calculate_checksum(tmp_path)
        
        # Extract text
        extraction_result = document_service.extract_text_from_pdf(tmp_path)
        
        extracted_text = extraction_result["text"]
        requires_ocr = extraction_result.get("requires_ocr", False)
        
        # Perform OCR if needed
        if requires_ocr and ocr_service.is_available():
            logger.info("PDF requires OCR - performing OCR")
            ocr_result = ocr_service.process_scanned_pdf(tmp_path)
            extracted_text = ocr_result["text"]
            extraction_result["ocr_performed"] = "yes"
            extraction_result["ocr_quality"] = ocr_result.get("quality_score", "unknown")
        
        # Store file
        storage_key = storage_service.generate_storage_key(
            analysis_id=str(analysis.id),
            filename=file.filename,
            prefix="documents"
        )
        storage_result = storage_service.save_file(tmp_path, storage_key)
        
        # Create document record
        document = UploadedDocument(
            analysis_id=analysis.id,
            filename=storage_key.split('/')[-1],
            original_filename=file.filename,
            file_type=DocumentType.PDF,
            file_size=len(content),
            checksum=checksum,
            storage_key=storage_key,
            storage_provider=storage_result["storage_provider"],
            extracted_text=extracted_text,
            ocr_performed=extraction_result.get("ocr_performed", "no"),
            ocr_quality_score=extraction_result.get("ocr_quality"),
        )
        db.add(document)
        
        # Generate explanation if we have text
        if extracted_text and extracted_text.strip():
            explanation_result = document_service.explain_report(
                report_text=extracted_text,
                language=analysis.language,
            )
            
            # Save explanation
            result = AnalysisResult(
                analysis_id=analysis.id,
                result_type=ResultType.EXPLANATION,
                content={"explanation": explanation_result["explanation"]},
                model_name=explanation_result["model"],
            )
            db.add(result)
            
            # Try structured extraction
            structured = document_service.extract_structured_findings(
                report_text=extracted_text,
                language=analysis.language,
            )
            if structured:
                structured_result = AnalysisResult(
                    analysis_id=analysis.id,
                    result_type=ResultType.STRUCTURED_FINDINGS,
                    content={"findings": structured},
                )
                db.add(structured_result)
        
        # Update analysis
        analysis.status = AnalysisStatus.COMPLETED
        analysis.processing_completed_at = datetime.utcnow()
        
        db.commit()
        
        # Clean up temp file
        tmp_path.unlink()
        
        logger.info(f"Document uploaded and processed: {document.id}")
        
        return {
            "document_id": str(document.id),
            "analysis_id": str(analysis.id),
            "filename": document.filename,
            "file_size": document.file_size,
            "extracted_text_length": len(extracted_text) if extracted_text else 0,
            "ocr_performed": document.ocr_performed,
        }
    
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ProcessingError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.error(f"Document upload failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document processing failed"
        )


@router.post("/analyses/{analysis_id}/images", status_code=status.HTTP_201_CREATED)
async def upload_radiology_image(
    analysis_id: str,
    file: UploadFile = File(...),
    body_part: str = Form("chest"),
    db: Session = Depends(get_db),
    client: IntegrationClient = Depends(require_authentication),
):
    """
    Upload an X-ray for AI analysis with a plain-English explanation.

    Accepts PNG, JPG, DICOM and PDF (first page). ``body_part="chest"`` (default)
    runs the chest X-ray model; ``"other"`` sends the image to a vision LLM for a
    general description of non-chest X-rays (the image is sent to Groq).
    The explanation covers an overall verdict, what was flagged, what looks
    normal, next steps and questions to ask a doctor.
    """
    try:
        analysis_uuid = UUID(analysis_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid analysis ID format"
        )
    
    analysis = db.query(MedicalAnalysis).filter(
        MedicalAnalysis.id == analysis_uuid
    ).first()
    
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found"
        )
    
    # Check access
    if client and not check_analysis_access(db, client, analysis_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Validate file type
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    
    body_part = body_part.lower()
    if body_part not in BODY_PARTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"body_part must be one of: {', '.join(BODY_PARTS)}"
        )
    
    tmp_path = None
    try:
        # Save uploaded file temporarily
        content = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(content)
            tmp_path = Path(tmp_file.name)
        
        # Analyze and explain (converts PDF/DICOM, runs model, writes plain English)
        report = build_report(tmp_path, body_part=body_part, language=analysis.language)
        
        # Store the original upload
        storage_service = StorageService()
        storage_key = storage_service.generate_storage_key(
            analysis_id=str(analysis.id),
            filename=file.filename,
            prefix="images"
        )
        storage_result = storage_service.save_file(tmp_path, storage_key)
        
        document = UploadedDocument(
            analysis_id=analysis.id,
            filename=storage_key.split('/')[-1],
            original_filename=file.filename,
            file_type=DOCUMENT_TYPES[suffix],
            file_size=len(content),
            checksum=storage_service.generate_storage_key(str(analysis.id), file.filename)[:64],
            storage_key=storage_key,
            storage_provider=storage_result["storage_provider"],
        )
        db.add(document)
        
        save_report(db, analysis, report)
        db.commit()
        
        logger.info(f"Radiology image processed: {document.id}")
        
        return {
            "document_id": str(document.id),
            "analysis_id": str(analysis.id),
            "modality": report["modality"],
            "model_name": report["model_name"],
            "overall": (report.get("summary") or {}).get("overall"),
            "explanation": report["explanation"],
            "generated_by": report["generated_by"],
            "num_findings": len(report["findings"]),
            "top_findings": report["findings"][:5],
        }
    
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ProcessingError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.error(f"Radiology image upload failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Radiology analysis failed"
        )
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
