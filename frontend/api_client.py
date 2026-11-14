"""
API Client for ClaraMed Backend

Handles all communication with the FastAPI backend.
"""
import os
import requests
from typing import Dict, Any, Optional
import streamlit as st

# Get backend URL from environment or use default
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API_KEY = os.getenv("CLARAMED_API_KEY")


class ClaraMedAPIClient:
    """Client for ClaraMed backend API."""
    
    def __init__(self, base_url: str = BACKEND_URL, api_key: Optional[str] = API_KEY):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        if api_key:
            self.session.headers["Authorization"] = f"Bearer {api_key}"
    
    def health_check(self) -> Dict[str, Any]:
        """Check API health."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/health",
                timeout=5
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    def readiness_check(self) -> Dict[str, Any]:
        """Check API readiness."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/health/ready",
                timeout=10
            )
            return response.json()
        except Exception as e:
            return {"status": "not_ready", "error": str(e)}
    
    def create_symptom_analysis(
        self,
        symptoms: str,
        language: str = "English",
        include_wellness: bool = True,
    ) -> Dict[str, Any]:
        """Create a new symptom analysis."""
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/analyses",
                json={
                    "symptoms": symptoms,
                    "language": language,
                    "include_wellness": include_wellness,
                },
                timeout=60
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    raise Exception(error_data.get("error", {}).get("message", str(e)))
                except:
                    raise Exception(f"API request failed: {str(e)}")
            raise Exception(f"API request failed: {str(e)}")
    
    def upload_document(
        self,
        analysis_id: str,
        file_content: bytes,
        filename: str,
    ) -> Dict[str, Any]:
        """Upload a medical document for analysis."""
        try:
            files = {"file": (filename, file_content, "application/pdf")}
            response = self.session.post(
                f"{self.base_url}/api/v1/analyses/{analysis_id}/documents",
                files=files,
                timeout=120
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    raise Exception(error_data.get("error", {}).get("message", str(e)))
                except:
                    raise Exception(f"Document upload failed: {str(e)}")
            raise Exception(f"Document upload failed: {str(e)}")
    
    def upload_radiology_image(
        self,
        analysis_id: str,
        file_content: bytes,
        filename: str,
    ) -> Dict[str, Any]:
        """Upload a radiology image for AI analysis."""
        try:
            # Determine content type
            if filename.lower().endswith('.png'):
                content_type = "image/png"
            elif filename.lower().endswith(('.jpg', '.jpeg')):
                content_type = "image/jpeg"
            else:
                content_type = "application/octet-stream"
            
            files = {"file": (filename, file_content, content_type)}
            response = self.session.post(
                f"{self.base_url}/api/v1/analyses/{analysis_id}/images",
                files=files,
                timeout=120
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    raise Exception(error_data.get("error", {}).get("message", str(e)))
                except:
                    raise Exception(f"Image upload failed: {str(e)}")
            raise Exception(f"Image upload failed: {str(e)}")
    
    def get_analysis_status(self, analysis_id: str) -> Dict[str, Any]:
        """Get analysis status."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/analyses/{analysis_id}",
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    raise Exception(error_data.get("error", {}).get("message", str(e)))
                except:
                    raise Exception(f"Failed to get status: {str(e)}")
            raise Exception(f"Failed to get status: {str(e)}")
    
    def get_analysis_results(self, analysis_id: str) -> Dict[str, Any]:
        """Get complete analysis results."""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/analyses/{analysis_id}/results",
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    raise Exception(error_data.get("error", {}).get("message", str(e)))
                except:
                    raise Exception(f"Failed to get results: {str(e)}")
            raise Exception(f"Failed to get results: {str(e)}")
    
    def list_analyses(
        self,
        page: int = 1,
        page_size: int = 20,
        analysis_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List analyses with pagination."""
        try:
            params = {"page": page, "page_size": page_size}
            if analysis_type:
                params["analysis_type"] = analysis_type
            
            response = self.session.get(
                f"{self.base_url}/api/v1/analyses",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    raise Exception(error_data.get("error", {}).get("message", str(e)))
                except:
                    raise Exception(f"Failed to list analyses: {str(e)}")
            raise Exception(f"Failed to list analyses: {str(e)}")


@st.cache_resource
def get_api_client() -> ClaraMedAPIClient:
    """Get cached API client instance."""
    return ClaraMedAPIClient()
