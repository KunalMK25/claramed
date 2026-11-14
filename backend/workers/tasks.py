"""
Celery Background Tasks

Defines background tasks for async processing.
"""
from celery import Task
from backend.workers.celery_app import celery_app
from backend.core.logging import get_logger
from backend.database.connection import get_db_context
from backend.models.analysis import MedicalAnalysis, AnalysisStatus, AnalysisType
from backend.models.result import AnalysisResult, ResultType
from backend.services.document_service import DocumentService
from backend.services.ocr_service import OCRService
from backend.services.radiology_report import build_report, save_report
from backend.services.storage_service import StorageService
from backend.core.exceptions import CorruptDocumentError, ValidationError
from pathlib import Path
from uuid import UUID
from datetime import datetime

logger = get_logger(__name__)


class NonRetryableError(Exception):
    """Deterministic bad input (corrupt image or PDF). Fail now; retrying cannot help."""


def finalize_after_task(analysis_id: str) -> None:
    """Integration lifecycle (delete source file, start retention, queue callback). Never raises."""
    try:
        from backend.workers.callbacks import finalize_integration_analysis  # lazy: avoids an import cycle
        with get_db_context() as db:
            finalize_integration_analysis(db, analysis_id)
    except Exception as exc:
        logger.error(f"Finalization failed: {exc}", analysis_id=analysis_id)


class AnalysisTask(Task):
    """Base task for analysis operations."""
    
    def on_success(self, retval, task_id, args, kwargs):
        """Finalize integration analyses once the work has completed."""
        if args:
            finalize_after_task(args[0])
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(
            f"Task failed: {task_id}",
            exception=str(exc),
            args=args,
            kwargs=kwargs,
        )
        
        # Update analysis status to failed
        if args and len(args) > 0:
            analysis_id = args[0]
            try:
                with get_db_context() as db:
                    analysis = db.query(MedicalAnalysis).filter(
                        MedicalAnalysis.id == UUID(analysis_id)
                    ).first()
                    
                    if analysis:
                        analysis.status = AnalysisStatus.FAILED
                        analysis.error_message = str(exc)
                        analysis.processing_completed_at = datetime.utcnow()
                        db.commit()
            except Exception as e:
                logger.error(f"Failed to update analysis status: {str(e)}")
            finalize_after_task(analysis_id)


@celery_app.task(bind=True, base=AnalysisTask, max_retries=3)
def process_document_async(self, analysis_id: str, document_id: str):
    """
    Process uploaded document asynchronously.
    
    Args:
        analysis_id: Analysis ID
        document_id: Document ID
    """
    logger.info(f"Processing document async: {document_id}")
    
    try:
        with get_db_context() as db:
            analysis = db.query(MedicalAnalysis).filter(
                MedicalAnalysis.id == UUID(analysis_id)
            ).first()
            
            if not analysis:
                raise ValueError(f"Analysis not found: {analysis_id}")
            
            if analysis.status == AnalysisStatus.FAILED:
                # Swept as stale (or failed earlier): a late worker must not overwrite that outcome.
                logger.info(f"Skipping already-failed analysis: {analysis_id}")
                return
            
            # Get document
            from backend.models.document import UploadedDocument
            document = db.query(UploadedDocument).filter(
                UploadedDocument.id == UUID(document_id)
            ).first()
            
            if not document:
                raise ValueError(f"Document not found: {document_id}")
            
            # Update analysis status
            analysis.status = AnalysisStatus.PROCESSING
            analysis.processing_started_at = datetime.utcnow()
            db.commit()
            
            # Initialize services
            storage_service = StorageService()
            document_service = DocumentService()
            ocr_service = OCRService()
            
            # Retrieve file from storage
            temp_path = storage_service.get_file(document.storage_key)
            
            try:
                # Extract text
                try:
                    extraction_result = document_service.extract_text_from_pdf(temp_path)
                except (ValidationError, CorruptDocumentError) as exc:
                    raise NonRetryableError(str(exc)) from exc
                extracted_text = extraction_result["text"]
                
                # Perform OCR if needed
                if extraction_result.get("requires_ocr") and ocr_service.is_available():
                    logger.info("Performing OCR on scanned document")
                    ocr_result = ocr_service.process_scanned_pdf(temp_path)
                    extracted_text = ocr_result["text"]
                    
                    # Update document with OCR info
                    document.ocr_performed = "yes"
                    document.ocr_quality_score = ocr_result.get("quality_score")
                
                # Update document with extracted text
                document.extracted_text = extracted_text
                
                # Generate explanation
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
                
                # Update analysis status
                analysis.status = AnalysisStatus.COMPLETED
                analysis.processing_completed_at = datetime.utcnow()
                
                db.commit()
                
                logger.info(f"Document processed successfully: {document_id}")
            
            finally:
                # Clean up temp file
                if temp_path.exists():
                    temp_path.unlink()
    
    except NonRetryableError:
        raise  # AnalysisTask.on_failure marks the analysis failed and finalizes it immediately
    except Exception as e:
        logger.error(f"Document processing failed: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=60)


@celery_app.task(bind=True, base=AnalysisTask, max_retries=3)
def process_radiology_async(self, analysis_id: str, image_id: str):
    """
    Process radiology image asynchronously.
    
    Args:
        analysis_id: Analysis ID
        image_id: Image document ID
    """
    logger.info(f"Processing radiology image async: {image_id}")
    
    try:
        with get_db_context() as db:
            analysis = db.query(MedicalAnalysis).filter(
                MedicalAnalysis.id == UUID(analysis_id)
            ).first()
            
            if not analysis:
                raise ValueError(f"Analysis not found: {analysis_id}")
            
            if analysis.status == AnalysisStatus.FAILED:
                # Swept as stale (or failed earlier): a late worker must not overwrite that outcome.
                logger.info(f"Skipping already-failed analysis: {analysis_id}")
                return
            
            # Get image document
            from backend.models.document import UploadedDocument
            
            image = db.query(UploadedDocument).filter(
                UploadedDocument.id == UUID(image_id)
            ).first()
            
            if not image:
                raise ValueError(f"Image not found: {image_id}")
            
            # Update analysis status
            analysis.status = AnalysisStatus.PROCESSING
            analysis.processing_started_at = datetime.utcnow()
            db.commit()
            
            # Retrieve image from storage
            storage_service = StorageService()
            temp_path = storage_service.get_file(image.storage_key)
            
            try:
                # Analyze and explain in plain English, then save everything
                try:
                    report = build_report(temp_path, language=analysis.language)
                except ValidationError as exc:
                    raise NonRetryableError(str(exc)) from exc
                save_report(db, analysis, report)
                db.commit()
                
                logger.info(f"Radiology image processed successfully: {image_id}")
            
            finally:
                # Clean up temp file
                if temp_path.exists():
                    temp_path.unlink()
    
    except NonRetryableError:
        raise
    except Exception as e:
        logger.error(f"Radiology processing failed: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=60)
