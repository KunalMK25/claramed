"""
Integration tests for document processing workflow.

Tests the complete flow from file upload through OCR/PDF extraction to LLM explanation.
"""
import pytest
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import io
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app
from backend.models.analysis import MedicalAnalysis, UploadedDocument
from backend.services.document_service import DocumentService
from backend.services.ocr_service import OCRService
from backend.ai.llm_provider import get_llm_provider


@pytest.fixture
def test_client():
    """Create test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def document_service(db_session):
    """Create document service instance."""
    return DocumentService(db_session)


@pytest.fixture
def ocr_service():
    """Create OCR service instance."""
    return OCRService()


@pytest.fixture
def sample_text_image():
    """
    Create a sample image with clear printed text for OCR testing.
    
    Simulates a scanned medical document.
    """
    # Create white background image
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)
    
    # Add sample medical text
    text = """MEDICAL RECORD
    
Patient presents with symptoms of:
- Persistent cough for 2 weeks
- Fever (101.5°F)
- Shortness of breath
- Fatigue

Assessment: Possible pneumonia
Plan: Order chest X-ray, CBC, start antibiotics
"""
    
    # Use default font (PIL doesn't guarantee specific fonts)
    try:
        # Try to use a clear font if available
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        # Fall back to default
        font = ImageFont.load_default()
    
    # Draw text on image
    draw.text((50, 50), text, fill='black', font=font)
    
    # Convert to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    return img_bytes


@pytest.fixture
def sample_medical_pdf(tmp_path):
    """
    Create a sample PDF with medical text for testing.
    
    Note: Creating actual PDFs requires reportlab or similar.
    For now, returns a text file path that DocumentService can handle.
    """
    # Create a temporary text file simulating PDF content
    # In real scenario, would use reportlab to create actual PDF
    pdf_content = """RADIOLOGY REPORT

Examination: Chest X-Ray PA and Lateral
Date: 2024-01-15

FINDINGS:
The lungs are clear without focal consolidation, pneumothorax, or pleural effusion.
The cardiac silhouette is normal in size and contour.
No acute osseous abnormality is identified.

IMPRESSION:
Normal chest radiograph. No acute cardiopulmonary disease.

Dictated by: Dr. Smith, MD
"""
    
    # For testing purposes, we'll create a text file
    # Real implementation would create actual PDF
    file_path = tmp_path / "sample_report.txt"
    file_path.write_text(pdf_content)
    
    return str(file_path)


class TestDocumentOCRWorkflow:
    """Test complete OCR workflow from image to extracted text."""
    
    def test_ocr_sample_image(self, ocr_service, sample_text_image):
        """Test OCR extraction from generated sample image."""
        # Reset stream position
        sample_text_image.seek(0)
        
        # Perform OCR
        result = ocr_service.extract_text_from_image(sample_text_image)
        
        # Verify result structure
        assert isinstance(result, dict)
        assert 'text' in result
        assert 'confidence' in result
        assert 'method' in result
        
        # Verify extracted text contains key medical terms
        text = result['text'].lower()
        assert len(text) > 0, "OCR should extract some text"
        
        # Check for expected keywords (OCR may not be perfect)
        # At least some medical context should be present
        expected_keywords = ['medical', 'patient', 'symptom', 'cough', 'fever']
        found_keywords = sum(1 for kw in expected_keywords if kw in text)
        
        assert found_keywords >= 2, f"Expected at least 2 medical keywords in OCR output, found {found_keywords}"
        
        # Verify confidence score is reasonable
        assert 0.0 <= result['confidence'] <= 100.0
        
        # Log result for manual verification
        print(f"\nOCR Result:")
        print(f"Confidence: {result['confidence']:.2f}")
        print(f"Text length: {len(result['text'])}")
        print(f"Sample text: {result['text'][:200]}")
    
    def test_pdf_text_extraction(self, document_service, sample_medical_pdf, db_session):
        """Test text extraction from PDF document."""
        # Read file content
        with open(sample_medical_pdf, 'rb') as f:
            file_content = f.read()
        
        # Process document (using text file instead of PDF for testing)
        # In real scenario would be actual PDF
        result = document_service.extract_text(
            file_content=file_content,
            filename="sample_report.pdf",
            content_type="application/pdf"
        )
        
        # Verify extraction
        assert isinstance(result, dict)
        assert 'text' in result
        assert 'page_count' in result
        
        # Verify content
        text = result['text']
        assert 'RADIOLOGY REPORT' in text
        assert 'FINDINGS' in text
        assert 'IMPRESSION' in text
        assert 'normal' in text.lower()
    
    @pytest.mark.skipif(
        not os.getenv("GROQ_API_KEY"),
        reason="Requires GROQ_API_KEY environment variable"
    )
    def test_document_explanation_with_llm(self, document_service, sample_medical_pdf):
        """Test LLM explanation generation for extracted document."""
        # Extract text first
        with open(sample_medical_pdf, 'rb') as f:
            file_content = f.read()
        
        extraction_result = document_service.extract_text(
            file_content=file_content,
            filename="sample_report.pdf",
            content_type="application/pdf"
        )
        
        # Generate explanation
        llm_provider = get_llm_provider()
        explanation = document_service.generate_explanation(
            text=extraction_result['text'],
            llm_provider=llm_provider
        )
        
        # Verify explanation
        assert isinstance(explanation, str)
        assert len(explanation) > 50, "Explanation should be substantial"
        
        # Should contain relevant medical context
        explanation_lower = explanation.lower()
        assert any(word in explanation_lower for word in ['chest', 'lung', 'radiograph', 'normal'])
        
        print(f"\nLLM Explanation: {explanation}")


class TestEndToEndDocumentAPI:
    """Test complete document upload and processing via API."""
    
    @pytest.mark.skipif(
        not os.getenv("GROQ_API_KEY"),
        reason="Requires GROQ_API_KEY environment variable"
    )
    def test_document_upload_and_processing(self, test_client, db_session, sample_text_image):
        """Test complete document upload flow via API."""
        # Create test client
        headers = {"X-API-Key": "test_key"}
        
        # Upload document
        sample_text_image.seek(0)
        files = {
            "file": ("medical_record.png", sample_text_image, "image/png")
        }
        data = {
            "document_type": "medical_record"
        }
        
        response = test_client.post(
            "/api/v1/analyses/documents",
            headers=headers,
            files=files,
            data=data
        )
        
        # Check response
        if response.status_code == 401:
            pytest.skip("API authentication required - test client needs valid key")
        
        assert response.status_code == 200
        result = response.json()
        
        assert 'analysis_id' in result
        assert 'status' in result
        assert result['status'] in ['pending', 'processing', 'completed']
        
        analysis_id = result['analysis_id']
        
        # Poll for completion (with timeout)
        import time
        max_wait = 30  # seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status_response = test_client.get(
                f"/api/v1/analyses/{analysis_id}/status",
                headers=headers
            )
            
            assert status_response.status_code == 200
            status_data = status_response.json()
            
            if status_data['status'] == 'completed':
                # Get results
                result_response = test_client.get(
                    f"/api/v1/analyses/{analysis_id}/result",
                    headers=headers
                )
                
                assert result_response.status_code == 200
                result_data = result_response.json()
                
                # Verify result structure
                assert 'analysis_type' in result_data
                assert 'result' in result_data
                
                print(f"\nDocument processing completed:")
                print(f"Analysis ID: {analysis_id}")
                print(f"Result: {result_data['result']}")
                
                return
            
            elif status_data['status'] == 'failed':
                pytest.fail(f"Analysis failed: {status_data.get('error', 'Unknown error')}")
            
            time.sleep(2)
        
        pytest.fail("Document processing did not complete within timeout")


class TestOCREdgeCases:
    """Test OCR service with various edge cases."""
    
    def test_empty_image(self, ocr_service):
        """Test OCR on blank image."""
        # Create blank white image
        img = Image.new('RGB', (200, 200), color='white')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        result = ocr_service.extract_text_from_image(img_bytes)
        
        # Should handle gracefully
        assert isinstance(result, dict)
        assert 'text' in result
        # Text may be empty or contain whitespace
        assert result['confidence'] >= 0.0
    
    def test_low_quality_image(self, ocr_service):
        """Test OCR on low-resolution image."""
        # Create small, low-quality image with text
        img = Image.new('RGB', (100, 50), color='white')
        draw = ImageDraw.Draw(img)
        draw.text((10, 10), "Test", fill='black')
        
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        result = ocr_service.extract_text_from_image(img_bytes)
        
        # Should handle without crashing
        assert isinstance(result, dict)
        # Confidence may be low for poor quality
        print(f"\nLow quality OCR confidence: {result['confidence']}")
    
    def test_rotated_text(self, ocr_service):
        """Test OCR on rotated text image."""
        # Create image with rotated text
        img = Image.new('RGB', (400, 400), color='white')
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("arial.ttf", 30)
        except:
            font = ImageFont.load_default()
        
        # Draw text normally first
        temp_img = Image.new('RGB', (300, 100), color='white')
        temp_draw = ImageDraw.Draw(temp_img)
        temp_draw.text((10, 10), "MEDICAL RECORD", fill='black', font=font)
        
        # Rotate the image
        rotated = temp_img.rotate(15, expand=True, fillcolor='white')
        
        # Paste onto main image
        img.paste(rotated, (50, 150))
        
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        result = ocr_service.extract_text_from_image(img_bytes)
        
        # OCR should attempt extraction (may not be perfect)
        assert isinstance(result, dict)
        print(f"\nRotated text OCR result: {result['text']}")
        print(f"Confidence: {result['confidence']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
