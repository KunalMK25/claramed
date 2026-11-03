"""
Integration tests for radiology analysis workflow.

Tests complete flow from X-ray image upload through TorchXRayVision inference.
"""
import pytest
import numpy as np
from PIL import Image
import io
import os
from fastapi.testclient import TestClient

from backend.services.radiology_service import RadiologyService
from backend.models.analysis import MedicalAnalysis, RadiologyFinding


@pytest.fixture
def radiology_service():
    """Create radiology service instance."""
    return RadiologyService()


@pytest.fixture
def test_client():
    """Create test client for FastAPI app."""
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def synthetic_chest_xray():
    """
    Create a synthetic chest X-ray-like image for testing.
    
    Note: This is NOT a real X-ray but simulates the format (grayscale, correct dimensions).
    For production validation, use real anonymized chest X-rays.
    """
    # Create 224x224 grayscale image (TorchXRayVision input size)
    # Simulate lung fields with darker center, brighter edges
    img_array = np.zeros((224, 224), dtype=np.uint8)
    
    # Create simple lung field pattern
    for i in range(224):
        for j in range(224):
            # Radial gradient from center
            dist_from_center = np.sqrt((i - 112)**2 + (j - 112)**2)
            # Lung fields are darker, chest wall brighter
            intensity = int(50 + (dist_from_center / 112) * 150)
            img_array[i, j] = min(255, intensity)
    
    # Add some random "pathology-like" regions for testing
    # Bright spot (simulating possible pneumothorax or artifact)
    img_array[50:70, 50:70] = 200
    
    # Darker region (simulating possible consolidation)
    img_array[150:180, 150:180] = 30
    
    # Convert to PIL Image
    img = Image.fromarray(img_array, mode='L')
    
    # Convert to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    return img_bytes


class TestRadiologyService:
    """Test radiology service directly."""
    
    def test_model_loading(self, radiology_service):
        """Test that TorchXRayVision model loads correctly."""
        # Model should be loaded on service initialization
        assert radiology_service.model is not None
        assert radiology_service.pathologies is not None
        assert len(radiology_service.pathologies) > 0
        
        print(f"\nLoaded pathologies: {radiology_service.pathologies}")
    
    def test_image_preprocessing(self, radiology_service, synthetic_chest_xray):
        """Test image preprocessing pipeline."""
        # Reset stream position
        synthetic_chest_xray.seek(0)
        
        # Load and preprocess image
        img_tensor = radiology_service.preprocess_image(synthetic_chest_xray)
        
        # Check tensor properties
        assert img_tensor is not None
        assert img_tensor.shape == (1, 1, 224, 224), "Expected batch of 1 grayscale 224x224 image"
        
        # Check value range (should be normalized)
        assert img_tensor.min() >= -5.0, "Values should be normalized"
        assert img_tensor.max() <= 5.0, "Values should be normalized"
        
        print(f"\nPreprocessed tensor shape: {img_tensor.shape}")
        print(f"Value range: [{img_tensor.min():.2f}, {img_tensor.max():.2f}]")
    
    def test_inference_on_synthetic_xray(self, radiology_service, synthetic_chest_xray):
        """Test full inference pipeline on synthetic X-ray."""
        # Reset stream position
        synthetic_chest_xray.seek(0)
        
        # Run inference
        result = radiology_service.analyze_image(synthetic_chest_xray)
        
        # Verify result structure
        assert isinstance(result, dict)
        assert 'findings' in result
        assert 'pathologies_detected' in result
        assert 'confidence_scores' in result
        
        # Verify findings structure
        findings = result['findings']
        assert isinstance(findings, list)
        
        # Each finding should have required fields
        for finding in findings:
            assert 'pathology' in finding
            assert 'confidence' in finding
            assert 0.0 <= finding['confidence'] <= 1.0
        
        # Verify confidence scores dictionary
        confidence_scores = result['confidence_scores']
        assert isinstance(confidence_scores, dict)
        assert len(confidence_scores) > 0
        
        # All pathologies should have scores
        for pathology, score in confidence_scores.items():
            assert isinstance(score, float)
            assert 0.0 <= score <= 1.0
        
        # Log results
        print(f"\nRadiology Analysis Results:")
        print(f"Pathologies detected: {result['pathologies_detected']}")
        print(f"Number of findings above threshold: {len(findings)}")
        if findings:
            print("\nFindings:")
            for finding in findings:
                print(f"  - {finding['pathology']}: {finding['confidence']:.3f}")
        
        print("\nAll confidence scores:")
        for pathology, score in sorted(confidence_scores.items(), key=lambda x: -x[1]):
            print(f"  {pathology}: {score:.3f}")
    
    def test_inference_with_real_xray_if_available(self, radiology_service, tmp_path):
        """
        Test inference on real chest X-ray if available in test data directory.
        
        This test is skipped if no real X-ray is available.
        """
        # Check for test X-ray image
        test_xray_path = os.path.join("tests", "data", "chest_xray_sample.png")
        
        if not os.path.exists(test_xray_path):
            pytest.skip("No real chest X-ray sample available for testing")
        
        # Load real X-ray
        with open(test_xray_path, 'rb') as f:
            xray_bytes = f.read()
        
        xray_stream = io.BytesIO(xray_bytes)
        
        # Run inference
        result = radiology_service.analyze_image(xray_stream)
        
        # Verify result
        assert isinstance(result, dict)
        assert 'findings' in result
        
        print(f"\nReal X-ray analysis:")
        print(f"Detected pathologies: {result['pathologies_detected']}")
        for finding in result['findings']:
            print(f"  - {finding['pathology']}: {finding['confidence']:.3f}")


class TestRadiologyAPI:
    """Test radiology endpoints via API."""
    
    def test_image_upload_endpoint(self, test_client, synthetic_chest_xray):
        """Test radiology image upload via API."""
        # Reset stream position
        synthetic_chest_xray.seek(0)
        
        headers = {"X-API-Key": "test_key"}
        files = {
            "file": ("chest_xray.png", synthetic_chest_xray, "image/png")
        }
        data = {
            "image_type": "chest_xray"
        }
        
        response = test_client.post(
            "/api/v1/analyses/images",
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
        
        print(f"\nImage upload response: {result}")
    
    @pytest.mark.skipif(
        not os.getenv("GROQ_API_KEY"),
        reason="Requires GROQ_API_KEY for full workflow"
    )
    def test_complete_radiology_workflow(self, test_client, synthetic_chest_xray):
        """Test complete radiology workflow from upload to result retrieval."""
        import time
        
        # Upload image
        synthetic_chest_xray.seek(0)
        headers = {"X-API-Key": "test_key"}
        files = {
            "file": ("chest_xray.png", synthetic_chest_xray, "image/png")
        }
        data = {
            "image_type": "chest_xray"
        }
        
        response = test_client.post(
            "/api/v1/analyses/images",
            headers=headers,
            files=files,
            data=data
        )
        
        if response.status_code == 401:
            pytest.skip("API authentication required")
        
        assert response.status_code == 200
        upload_result = response.json()
        analysis_id = upload_result['analysis_id']
        
        # Poll for completion
        max_wait = 60  # seconds (inference can take time on CPU)
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status_response = test_client.get(
                f"/api/v1/analyses/{analysis_id}/status",
                headers=headers
            )
            
            assert status_response.status_code == 200
            status_data = status_response.json()
            
            print(f"Status: {status_data['status']}")
            
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
                assert result_data['analysis_type'] == 'radiology'
                assert 'result' in result_data
                
                # Check for radiology-specific data
                result_obj = result_data['result']
                assert 'findings' in result_obj or 'pathologies_detected' in result_obj
                
                print(f"\nRadiology workflow completed:")
                print(f"Analysis ID: {analysis_id}")
                print(f"Result: {result_obj}")
                
                return
            
            elif status_data['status'] == 'failed':
                pytest.fail(f"Analysis failed: {status_data.get('error', 'Unknown error')}")
            
            time.sleep(3)
        
        pytest.fail("Radiology processing did not complete within timeout")


class TestRadiologyEdgeCases:
    """Test edge cases for radiology analysis."""
    
    def test_invalid_image_format(self, radiology_service):
        """Test handling of invalid image format."""
        # Create invalid image data
        invalid_data = io.BytesIO(b"not an image")
        
        with pytest.raises(Exception):
            radiology_service.analyze_image(invalid_data)
    
    def test_wrong_size_image(self, radiology_service):
        """Test handling of incorrectly sized images."""
        # Create very small image
        img = Image.new('L', (50, 50), color=128)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        # Should still process (service should resize)
        result = radiology_service.analyze_image(img_bytes)
        
        # Should return valid result structure even if quality is poor
        assert isinstance(result, dict)
        assert 'findings' in result
    
    def test_color_image_conversion(self, radiology_service):
        """Test conversion of color image to grayscale."""
        # Create RGB image (X-rays should be grayscale)
        img = Image.new('RGB', (224, 224), color=(100, 100, 100))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        # Should handle color-to-grayscale conversion
        result = radiology_service.analyze_image(img_bytes)
        
        assert isinstance(result, dict)
        assert 'findings' in result


class TestModelPerformanceCharacteristics:
    """Document model performance characteristics for validation."""
    
    def test_inference_time(self, radiology_service, synthetic_chest_xray):
        """Measure and report inference time."""
        import time
        
        synthetic_chest_xray.seek(0)
        
        start_time = time.time()
        result = radiology_service.analyze_image(synthetic_chest_xray)
        end_time = time.time()
        
        inference_time = end_time - start_time
        
        print(f"\nInference time: {inference_time:.2f} seconds")
        print(f"Device: {'CUDA' if radiology_service.device == 'cuda' else 'CPU'}")
        
        # Document for performance tracking
        # Production deployments should target <5s on GPU, <30s on CPU
        assert inference_time < 120, "Inference took too long - check system resources"
    
    def test_confidence_distribution(self, radiology_service, synthetic_chest_xray):
        """Analyze confidence score distribution."""
        synthetic_chest_xray.seek(0)
        
        result = radiology_service.analyze_image(synthetic_chest_xray)
        confidence_scores = result['confidence_scores']
        
        # Calculate statistics
        scores = list(confidence_scores.values())
        mean_conf = np.mean(scores)
        std_conf = np.std(scores)
        max_conf = np.max(scores)
        
        print(f"\nConfidence score statistics:")
        print(f"  Mean: {mean_conf:.3f}")
        print(f"  Std Dev: {std_conf:.3f}")
        print(f"  Max: {max_conf:.3f}")
        print(f"  Number above 0.5 threshold: {sum(1 for s in scores if s > 0.5)}")
        
        # Sanity checks
        assert 0.0 <= mean_conf <= 1.0
        assert max_conf <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
