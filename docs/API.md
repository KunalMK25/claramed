# ClaraMed API Documentation

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

Currently optional for development. For production, use Bearer token authentication:

```
Authorization: Bearer <api_key>
```

## Endpoints

### Health Check

#### GET /health

Basic health check.

**Response:**
```json
{
  "status": "healthy",
  "name": "ClaraMed",
  "version": "1.0.0",
  "environment": "development",
  "timestamp": "2026-11-01T12:00:00"
}
```

#### GET /health/ready

Readiness check with dependency status.

**Response:**
```json
{
  "status": "ready",
  "checks": {
    "database": {"status": "healthy"},
    "ocr": {"status": "available"},
    "radiology_ai": {"status": "available"},
    "llm": {"status": "configured"}
  }
}
```

### Symptom Analysis

#### POST /analyses

Create a new symptom analysis.

**Request:**
```json
{
  "symptoms": "I have a headache and feel nauseous",
  "language": "English",
  "include_wellness": true,
  "external_patient_reference": "patient_123",
  "external_hospital_reference": "hospital_456"
}
```

**Response (201 Created):**
```json
{
  "analysis_id": "uuid",
  "status": "completed",
  "analysis_type": "symptom",
  "language": "English",
  "emergency_classification": {
    "emergency_flagged": false,
    "message": null
  },
  "explanation": "Based on your symptoms...",
  "wellness_tips": "### Diet Suggestions...",
  "created_at": "2026-11-01T12:00:00",
  "processing_duration_seconds": 2.5
}
```

### Document Upload

#### POST /analyses/{analysis_id}/documents

Upload a medical document for analysis.

**Request:** Multipart form-data
- `file`: PDF file (max 10MB)

**Response (201 Created):**
```json
{
  "document_id": "uuid",
  "analysis_id": "uuid",
  "filename": "report.pdf",
  "file_size": 524288,
  "extracted_text_length": 1500,
  "ocr_performed": "yes"
}
```

### Radiology Image Upload

#### POST /analyses/{analysis_id}/images

Upload a chest X-ray for AI analysis.

**Request:** Multipart form-data
- `file`: Image file (PNG, JPEG, JPG)

**Response (201 Created):**
```json
{
  "document_id": "uuid",
  "analysis_id": "uuid",
  "modality": "chest_xray",
  "model_name": "densenet121-res224-all",
  "num_findings": 14,
  "top_findings": [
    {
      "label": "Cardiomegaly",
      "model_score": 0.123
    }
  ]
}
```

### Get Analysis Status

#### GET /analyses/{analysis_id}

Get analysis processing status.

**Response:**
```json
{
  "analysis_id": "uuid",
  "status": "completed",
  "analysis_type": "symptom",
  "created_at": "2026-11-01T12:00:00",
  "updated_at": "2026-11-01T12:00:05",
  "processing_started_at": "2026-11-01T12:00:01",
  "processing_completed_at": "2026-11-01T12:00:05"
}
```

### Get Analysis Results

#### GET /analyses/{analysis_id}/results

Get complete analysis results.

**Response:**
```json
{
  "analysis_id": "uuid",
  "status": "completed",
  "analysis_type": "symptom",
  "language": "English",
  "results": {
    "explanation": {
      "explanation": "..."
    },
    "wellness_tips": {
      "wellness_tips": "..."
    }
  },
  "created_at": "2026-11-01T12:00:00",
  "completed_at": "2026-11-01T12:00:05"
}
```

### List Analyses

#### GET /analyses

List analyses with pagination.

**Query Parameters:**
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20, max: 100)
- `analysis_type`: Filter by type (symptom, report_pdf, xray)

**Response:**
```json
{
  "analyses": [...],
  "total": 50,
  "page": 1,
  "page_size": 20
}
```

## Error Responses

All errors follow this format:

```json
{
  "error": {
    "message": "Error description",
    "details": {},
    "request_id": "uuid"
  }
}
```

**Common Status Codes:**
- 400: Bad Request (invalid input)
- 401: Unauthorized (missing/invalid API key)
- 403: Forbidden (insufficient permissions)
- 404: Not Found (resource not found)
- 422: Unprocessable Entity (processing failed)
- 429: Too Many Requests (rate limit exceeded)
- 500: Internal Server Error
- 503: Service Unavailable (dependencies unavailable)
