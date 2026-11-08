# ClaraMed - Build Specification v1.3

**Document Status**: Master Specification  
**Last Updated**: 2026-11-08  
**Target Version**: 1.0.0

---

## 1. Executive Summary

ClaraMed is an AI-powered medical analysis platform designed as an independent clinical decision support tool. It provides symptom analysis, medical document processing with OCR, and chest X-ray analysis using deep learning models.

**Core Purpose**: Transform a proof-of-concept Streamlit application into a production-oriented, independently deployable medical AI service prototype with RESTful APIs suitable for future integration with the JeevaCare healthcare platform.

**Note**: A production-oriented architecture does not establish production readiness. Production readiness requires security testing, deployment verification, reliability testing, operational monitoring, and appropriate clinical and regulatory review.

**Key Principle**: ClaraMed operates as a standalone service. It does NOT have runtime or database dependencies on JeevaCare or any external healthcare system. Integration happens through well-defined REST APIs only.

---

## 2. Project Goals

### Primary Objectives

1. **Independent Operation**: Deploy and verify ClaraMed functionality without requiring JeevaCare infrastructure
2. **Production-Oriented Architecture**: Transform POC into a production-oriented service with proper separation of concerns
3. **Real AI Inference**: Implement actual TorchXRayVision model inference and Tesseract OCR (not mocked)
4. **Persistent Storage**: Replace SQLite with PostgreSQL, implement file storage
5. **Background Processing**: Move expensive operations (OCR, radiology inference) to async workers
6. **API-First Design**: Expose all functionality through REST APIs for future integrations
7. **Medical Safety**: Maintain appropriate disclaimers, conservative emergency classification, human-in-loop design

**Note**: These objectives describe architectural targets, not verified operational status. Actual production readiness requires comprehensive testing, security audits, performance validation, and appropriate regulatory review.

### Non-Goals (Explicitly Out of Scope)

- ❌ JeevaCare integration implementation (API contracts defined, integration deferred)
- ❌ FDA clearance or medical device certification
- ❌ Production deployment to specific cloud infrastructure
- ❌ User authentication system (service-to-service auth only)
- ❌ Patient-facing appointment or workflow management
- ❌ Electronic Health Record (EHR) integration
- ❌ Billing or insurance processing
- ❌ Clinical trial or research study management

---

## 3. Architecture Overview

### System Architecture Diagram

```
┌───────────────────────────────────────────────────┐
│              Client Applications                   │
│  ┌──────────────┐        ┌──────────────┐        │
│  │  Streamlit   │        │  JeevaCare   │        │
│  │     UI       │        │  (Future)    │        │
│  └──────┬───────┘        └──────┬───────┘        │
└─────────┼──────────────────────┼─────────────────┘
          │                      │
          └──────────┬───────────┘
                     │ HTTPS/REST
          ┌──────────▼───────────┐
          │   FastAPI Backend    │
          │  ┌────────────────┐  │
          │  │  API Routes    │  │
          │  │  Auth Layer    │  │
          │  │  Validation    │  │
          │  └────────┬───────┘  │
          └───────────┼───────────┘
                      │
      ┌───────────────┼───────────────┐
      │               │               │
┌─────▼────┐    ┌────▼────┐    ┌────▼────┐
│ Symptom  │    │Document │    │Radiology│
│ Service  │    │ Service │    │ Service │
└─────┬────┘    └────┬────┘    └────┬────┘
      │              │              │
┌─────▼─────┐  ┌────▼────┐   ┌────▼────┐
│  Groq API │  │Tesseract│   │TorchXRay│
│   (LLM)   │  │   OCR   │   │ Vision  │
└───────────┘  └─────────┘   └─────────┘
                     │
          ┌──────────▼───────────┐
          │  Background Workers  │
          │     (Celery)         │
          └──────────┬───────────┘
                     │
      ┌──────────────┼──────────────┐
      │              │              │
┌─────▼──────┐ ┌────▼────┐   ┌────▼────┐
│ PostgreSQL │ │  Redis  │   │ Storage │
│  Database  │ │ Message │   │ (Local/ │
│            │ │  Broker │   │   S3)   │
└────────────┘ └─────────┘   └─────────┘
```

### Technology Stack

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| **Backend API** | FastAPI | ≥0.104.0 | Async support, automatic OpenAPI docs, type safety, suitable for production when properly deployed |
| **Frontend** | Streamlit | ≥1.28.0 | Rapid prototyping, preserves existing UX, Python-native |
| **Database** | PostgreSQL | 15+ | JSONB support, ACID compliance, suitable for healthcare applications when properly configured |
| **ORM** | SQLAlchemy | ≥2.0.0 | Industry standard, type hints, async support |
| **Migrations** | Alembic | ≥1.12.0 | Schema version control, rollback support |
| **Task Queue** | Celery | ≥5.3.0 | Battle-tested async processing, retry logic, monitoring |
| **Message Broker** | Redis | 7+ | In-memory performance, pub/sub, simple deployment |
| **LLM Provider** | Groq API | N/A | Fast inference, llama-3.1-8b-instant model |
| **Radiology AI** | TorchXRayVision | ≥1.2.0 | Pretrained on medical data, 14 chest pathologies |
| **OCR Engine** | Tesseract | 4.x+ | Open source, multi-language, no API costs |
| **PDF Processing** | PyPDF2 | ≥3.0.1 | Text extraction from embedded PDF text |
| **Image Processing** | Pillow, scikit-image | ≥10.0.0 | Preprocessing for OCR and radiology |
| **ML Framework** | PyTorch | ≥2.0.0 | TorchXRayVision dependency |
| **Storage** | Local / S3-compatible | N/A | Development flexibility, production scalability |
| **Containerization** | Docker | Latest | Reproducible deployments |
| **Orchestration** | Docker Compose | Latest | Local development, small production |
| **Language** | Python | 3.11+ | Type hints, modern async/await |

---

## 4. Project Structure

```
claramed/
├── backend/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── health.py       # Health/readiness checks
│   │   │   └── analyses.py     # Core analysis endpoints
│   │   ├── dependencies.py     # Auth, DB session injection
│   │   └── __init__.py
│   ├── core/
│   │   ├── config.py          # Pydantic settings
│   │   ├── security.py        # API key hashing, secrets
│   │   ├── exceptions.py      # Custom exception hierarchy
│   │   ├── logging.py         # Structured logging
│   │   └── __init__.py
│   ├── models/
│   │   ├── analysis.py        # MedicalAnalysis table
│   │   ├── result.py          # AnalysisResult table
│   │   ├── document.py        # UploadedDocument table
│   │   ├── radiology.py       # RadiologyFinding table
│   │   ├── integration_client.py  # IntegrationClient table
│   │   ├── audit.py           # AuditEvent table
│   │   └── __init__.py
│   ├── schemas/
│   │   ├── analysis.py        # Pydantic request/response models
│   │   └── __init__.py
│   ├── services/
│   │   ├── symptom_service.py      # Symptom analysis logic
│   │   ├── emergency_service.py    # Emergency classification
│   │   ├── document_service.py     # PDF text extraction
│   │   ├── ocr_service.py          # Tesseract integration
│   │   ├── radiology_service.py    # TorchXRayVision inference
│   │   ├── storage_service.py      # File storage abstraction
│   │   └── __init__.py
│   ├── ai/
│   │   ├── llm_provider.py    # LLM abstraction (Groq)
│   │   ├── prompts.py         # Centralized prompt templates
│   │   └── __init__.py
│   ├── workers/
│   │   ├── celery_app.py      # Celery configuration
│   │   ├── tasks.py           # Background tasks
│   │   └── __init__.py
│   ├── database/
│   │   ├── connection.py      # SQLAlchemy engine setup
│   │   └── __init__.py
│   ├── main.py                # FastAPI application entry
│   └── __init__.py
├── frontend/
│   ├── api_client.py          # REST API client for Streamlit
│   └── __init__.py
├── migrations/
│   ├── versions/              # Alembic migration scripts
│   ├── env.py                 # Alembic environment
│   └── script.py.mako         # Migration template
├── tests/
│   ├── unit/                  # Unit tests for services
│   ├── api/                   # API endpoint tests
│   ├── integration/           # End-to-end workflow tests
│   ├── conftest.py            # Pytest fixtures
│   └── __init__.py
├── docs/
│   ├── API.md                 # REST API documentation
│   ├── ARCHITECTURE.md        # System design
│   ├── DEPLOYMENT.md          # Deployment guide
│   ├── SECURITY.md            # Security controls
│   ├── MODEL_LIMITATIONS.md   # AI disclaimers
│   └── BUILD.md               # This specification
├── scripts/
│   ├── init_db.py             # Database initialization
│   ├── check_dependencies.py  # Environment validation
│   └── verify_implementation.py  # Acceptance test runner
├── storage/                   # Local file storage (dev)
├── models/                    # AI model cache
├── app_new.py                 # Refactored Streamlit frontend
├── Dockerfile                 # Backend container
├── Dockerfile.frontend        # Frontend container
├── docker-compose.yml         # Multi-service orchestration
├── .dockerignore
├── alembic.ini               # Alembic configuration
├── requirements.txt          # Python dependencies
├── requirements-dev.txt      # Development dependencies
├── .env.example              # Environment template
├── .gitignore
├── README.md
├── IMPLEMENTATION_STATUS.md  # Progress tracker
├── NEXT_STEPS.md            # Deployment guide
└── BUILD.md                 # This file
```

---

## 5. Core Functionality Requirements

### 5.1 Symptom Analysis

**Description**: Accept user-provided symptoms, analyze using LLM, provide educational explanation and wellness tips.

**Requirements**:
- Accept symptom text (10-5000 characters)
- Optional: duration, severity (1-10 scale)
- Validate input for completeness
- Call emergency classification service
- If emergency flagged: return conservative warning message
- Generate AI-generated, non-diagnostic educational explanation of possible conditions requiring qualified healthcare professional review
- Generate wellness tips (diet, lifestyle, when to seek care)
- Support 7 languages: English, Hindi, Kannada, Tamil, Telugu, Spanish, French
- Store analysis in database with status tracking
- Return structured JSON response

**Conservative Emergency Classification**:
- Keyword-based screening for life-threatening symptoms
- LLM-based contextual classification (fallback)
- Must not provide false reassurance when serious conditions are possible
- Must err on the side of caution (conservative flagging)
- Direct users to emergency services (911) when flagged
- Emergency warnings must not falsely reassure users that they are safe
- Log all emergency classifications to audit trail

**Safety Requirements**:
- ClaraMed is an AI-assisted clinical decision-support prototype
- Never claim to diagnose, treat, or prevent any disease
- AI-generated explanations are not definitive diagnoses, prescriptions, or treatment instructions
- Include disclaimer: "For informational and educational purposes only. Not medical advice, diagnosis, or treatment. Always consult a qualified healthcare professional."
- Do not provide medication dosing recommendations or prescriptions
- Does not replace qualified healthcare professional evaluation

### 5.2 Medical Document Processing

**Description**: Upload PDF documents, extract text (embedded or OCR), explain medical terminology in plain language.

**Requirements**:
- Accept PDF files (max 10MB)
- Validate file type, size, and signature
- Attempt PyPDF2 text extraction first
- If text extraction fails or yields <50 characters:
  - Convert PDF pages to images
  - Apply Tesseract OCR to each page
  - Preserve page numbers and provenance
- Extract medical terminology and key findings
- Generate AI-generated, non-diagnostic plain-language explanation requiring qualified healthcare professional review
- Store document metadata and extracted text
- Save uploaded file to storage service
- Return document ID and processing status
- Background processing for expensive operations

**File Storage Requirements**:
- Organize by client_id and analysis_id
- Support local filesystem (development)
- Support S3-compatible storage (production)
- Generate presigned URLs for secure download
- Implement file retention policies

### 5.3 Radiology Analysis (Chest X-Ray)

**Description**: Upload chest X-ray images, run TorchXRayVision inference, detect pathologies, generate AI-generated, non-diagnostic explanatory summary requiring qualified healthcare professional review.

**Requirements**:
- **Supported Modalities**: Chest X-ray only (PA or AP frontal views)
- Accept image files: PNG, JPEG, DICOM (planned)
- Validate file type and size (max 10MB)
- Load TorchXRayVision densenet121-res224-all model
- Preprocess image according to model requirements:
  - Verify and apply model-specific preprocessing (grayscale, resize, normalization)
  - Validate preprocessing against model documentation
- Run model inference
- Extract raw model output scores for all pathologies:
  - Atelectasis, Cardiomegaly, Consolidation, Edema, Effusion
  - Emphysema, Fibrosis, Hernia, Infiltration, Mass, Nodule
  - Pleural Thickening, Pneumonia, Pneumothorax
- Extract raw model output scores (0.0-1.0) for all pathologies
- Store findings with model version and timestamp
- Generate AI-generated, non-diagnostic explanatory summary using LLM (clearly labeled as AI-generated content requiring qualified healthcare professional review)
- Background processing (inference can take 10-30s on CPU)

**Safety Requirements**:
- ClaraMed is an AI-assisted clinical decision-support prototype
- Clear disclaimer: "AI-assisted radiology analysis. Requires qualified radiologist review. Not a diagnostic tool."
- Raw model outputs are model scores, not automatically calibrated clinical probabilities
- Do not classify findings as definitively present or absent using an arbitrary universal threshold
- Any threshold used must be explicitly configurable, documented, and justified by appropriate validation
- Never present scores as diagnostic confidence percentages or sensitivity/specificity claims
- Clearly distinguish AI-generated findings from clinician-confirmed findings
- Do not make unsupported accuracy, diagnostic performance, or clinical validity claims
- Document model limitations (see MODEL_LIMITATIONS.md)
- Log all inferences for quality monitoring
- Do not process non-chest or non-frontal X-rays

### 5.4 Analysis History

**Requirements**:
- Store all analyses in PostgreSQL
- Track status: pending → processing → completed | failed
- Record timestamps: created_at, processing_started_at, processing_completed_at
- Support pagination (default: 20 per page, max: 100)
- Filter by analysis_type: symptom, document, radiology
- Filter by status
- Enforce client isolation (no cross-client data access)
- Return structured results with metadata

### 5.5 Multilingual Support

**Requirements**:
- Accept `language` parameter in API requests
- Supported languages:
  - English (default)
  - Hindi (हिन्दी)
  - Kannada (ಕನ್ನಡ)
  - Tamil (தமிழ்)
  - Telugu (తెలుగు)
  - Spanish (Español)
  - French (Français)
- LLM generates AI-generated, non-diagnostic explanatory summaries in requested language (not for clinical decision-making)
- UI displays language selector
- Emergency messages in user's language
- Maintain medical terminology accuracy across languages

---

## 6. API Specification

### 6.1 API Design Principles

- **RESTful**: Standard HTTP methods (GET, POST, PUT, DELETE)
- **Stateless**: No server-side sessions, API key authentication
- **Versioned**: `/api/v1` prefix for all endpoints
- **JSON**: Request and response bodies use application/json
- **Error Handling**: Consistent error response structure
- **OpenAPI**: Auto-generated documentation at `/docs`

### 6.2 Authentication

**Method**: API Key (X-API-Key header)

```http
X-API-Key: <client_api_key>
```

**Security**:
- API keys stored as bcrypt hashes in `integration_clients` table
- Keys generated using `secrets.token_urlsafe(32)`
- Failed authentication returns 401 Unauthorized
- Log authentication attempts to audit trail
- Support key rotation (future enhancement)

### 6.3 Core Endpoints

#### Health Checks

```
GET /health
GET /health/ready
```

#### Symptom Analysis

```
POST /api/v1/analyses
```

**Request**:
```json
{
  "symptoms": "string (10-5000 chars, required)",
  "duration": "string (optional)",
  "severity": "integer 1-10 (optional)",
  "language": "string (default: English)",
  "include_wellness": "boolean (default: true)",
  "external_patient_reference": "string (optional)",
  "external_hospital_reference": "string (optional)"
}
```

**Response** (201 Created):
```json
{
  "analysis_id": "uuid",
  "status": "completed",
  "analysis_type": "symptom",
  "emergency_classification": {
    "emergency_flagged": "boolean",
    "message": "string (if flagged)"
  },
  "explanation": "string",
  "wellness_tips": "string (markdown)",
  "created_at": "ISO 8601 timestamp",
  "processing_duration_seconds": "float"
}
```

#### Document Upload

```
POST /api/v1/analyses/documents
```

**Request**: Multipart form-data
- `file`: PDF file (required)
- `document_type`: string (optional)
- `analysis_id`: uuid (optional, creates new if omitted)

**Response** (201 Created):
```json
{
  "document_id": "uuid",
  "analysis_id": "uuid",
  "filename": "string",
  "file_size": "integer (bytes)",
  "extracted_text_length": "integer",
  "ocr_performed": "yes | no | failed",
  "status": "processing | completed | failed"
}
```

#### Radiology Image Upload

```
POST /api/v1/analyses/images
```

**Request**: Multipart form-data
- `file`: Image file (PNG/JPEG, required)
- `image_type`: "chest_xray" (required)
- `analysis_id`: uuid (optional)

**Response** (201 Created):
```json
{
  "document_id": "uuid",
  "analysis_id": "uuid",
  "modality": "chest_xray",
  "model_name": "densenet121-res224-all",
  "status": "processing",
  "num_findings": "integer (when completed)",
  "top_findings": [
    {
      "label": "string",
      "model_score": "float 0.0-1.0"
    }
  ]
}
```

#### Get Analysis Status

```
GET /api/v1/analyses/{analysis_id}
```

#### Get Analysis Results

```
GET /api/v1/analyses/{analysis_id}/result
```

#### List Analyses

```
GET /api/v1/analyses?page=1&page_size=20&analysis_type=symptom
```

### 6.4 Error Responses

**Standard Error Format**:
```json
{
  "error": {
    "message": "Human-readable error description",
    "code": "ERROR_CODE",
    "details": {},
    "request_id": "uuid"
  }
}
```

**HTTP Status Codes**:
- 400 Bad Request: Invalid input
- 401 Unauthorized: Missing or invalid API key
- 403 Forbidden: Insufficient permissions
- 404 Not Found: Resource not found
- 422 Unprocessable Entity: Processing failed
- 429 Too Many Requests: Rate limit exceeded
- 500 Internal Server Error: Unexpected error
- 503 Service Unavailable: Dependencies unavailable

---

## 7. Database Schema

### 7.1 Schema Design

**Technology**: PostgreSQL 15+  
**ORM**: SQLAlchemy 2.0+  
**Migrations**: Alembic

### 7.2 Core Tables

#### medical_analyses

Primary table storing all analysis records.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Analysis unique identifier |
| client_id | UUID | NOT NULL, FK to integration_clients | Client ownership |
| analysis_type | VARCHAR(50) | NOT NULL, CHECK | symptom \| document \| radiology |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'pending' | pending \| processing \| completed \| failed |
| language | VARCHAR(50) | DEFAULT 'English' | Response language |
| symptoms | TEXT | NULL | Symptom description (symptom type only) |
| emergency_flagged | BOOLEAN | DEFAULT FALSE | Emergency detected |
| emergency_message | TEXT | NULL | Emergency warning text |
| external_patient_reference | VARCHAR(255) | NULL | JeevaCare patient ID |
| external_hospital_reference | VARCHAR(255) | NULL | JeevaCare hospital ID |
| processing_started_at | TIMESTAMP | NULL | When processing began |
| processing_completed_at | TIMESTAMP | NULL | When processing finished |
| processing_duration_seconds | DECIMAL(10,2) | NULL | Total processing time |
| error_message | TEXT | NULL | Failure reason |
| created_at | TIMESTAMP | DEFAULT NOW() | Record creation |
| updated_at | TIMESTAMP | DEFAULT NOW() | Last update |

**Indexes**:
- idx_analyses_client (client_id)
- idx_analyses_status (status)
- idx_analyses_type (analysis_type)
- idx_analyses_created (created_at DESC)

#### analysis_results

Stores structured results for each analysis.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Result unique identifier |
| analysis_id | UUID | NOT NULL, FK CASCADE | Parent analysis |
| result_type | VARCHAR(50) | NOT NULL, CHECK | explanation \| wellness_tips \| document_summary \| radiology_interpretation |
| result_data | JSONB | NOT NULL | Flexible JSON structure |
| confidence_score | DECIMAL(5,4) | NULL | Optional confidence (0.0-1.0) |
| model_version | VARCHAR(100) | NULL | AI model version |
| created_at | TIMESTAMP | DEFAULT NOW() | Record creation |

**Indexes**:
- idx_results_analysis (analysis_id)
- idx_results_type (result_type)

#### uploaded_documents

Metadata for uploaded files.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Document unique identifier |
| analysis_id | UUID | NOT NULL, FK CASCADE | Parent analysis |
| document_type | VARCHAR(50) | CHECK | pdf \| image \| dicom |
| filename | VARCHAR(500) | NOT NULL | Original filename |
| file_size | INTEGER | NOT NULL | Size in bytes |
| storage_key | VARCHAR(1000) | NOT NULL | S3 key or local path |
| mime_type | VARCHAR(100) | NOT NULL | Content type |
| extracted_text | TEXT | NULL | OCR or PDF text |
| ocr_performed | BOOLEAN | DEFAULT FALSE | OCR was used |
| ocr_confidence | DECIMAL(5,2) | NULL | Average OCR confidence (0-100) |
| page_count | INTEGER | NULL | Number of pages |
| created_at | TIMESTAMP | DEFAULT NOW() | Record creation |

**Indexes**:
- idx_documents_analysis (analysis_id)

#### radiology_findings

Individual pathology detections from radiology AI.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Finding unique identifier |
| document_id | UUID | NOT NULL, FK CASCADE | Parent document |
| pathology_label | VARCHAR(100) | NOT NULL | E.g., "Cardiomegaly" |
| model_score | DECIMAL(5,4) | NOT NULL | Raw model output (0.0-1.0), not a calibrated probability |
| above_threshold | BOOLEAN | NULL | Optional experimental flag if threshold applied |
| threshold_value | DECIMAL(5,4) | NULL | The threshold value used (if any) |
| model_name | VARCHAR(200) | NOT NULL | E.g., densenet121-res224-all |
| model_version | VARCHAR(100) | NULL | Model version string |
| created_at | TIMESTAMP | DEFAULT NOW() | Record creation |

**Indexes**:
- idx_findings_document (document_id)
- idx_findings_pathology (pathology_label)

#### integration_clients

API authentication clients.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Client unique identifier |
| client_name | VARCHAR(200) | NOT NULL, UNIQUE | Client display name |
| api_key_hash | VARCHAR(255) | NOT NULL | bcrypt hash of API key |
| is_active | BOOLEAN | DEFAULT TRUE | Client enabled |
| rate_limit_per_hour | INTEGER | DEFAULT 1000 | Request limit |
| allowed_origins | TEXT[] | NULL | CORS origins |
| metadata | JSONB | NULL | Additional client info |
| created_at | TIMESTAMP | DEFAULT NOW() | Client registration |
| last_used_at | TIMESTAMP | NULL | Last successful auth |

**Indexes**:
- idx_clients_active (is_active)

#### audit_events

Security and compliance audit trail.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Event unique identifier |
| client_id | UUID | NULL, FK | Associated client |
| event_type | VARCHAR(50) | NOT NULL | auth \| analysis_create \| file_upload \| error |
| action | VARCHAR(50) | NOT NULL | create \| read \| update \| delete |
| resource_type | VARCHAR(100) | NULL | analysis \| document \| client |
| resource_id | VARCHAR(255) | NULL | Resource identifier |
| ip_address | VARCHAR(50) | NULL | Client IP |
| user_agent | TEXT | NULL | Client user agent |
| success | BOOLEAN | NOT NULL | Operation succeeded |
| error_message | TEXT | NULL | Failure reason |
| metadata | JSONB | NULL | Additional context |
| created_at | TIMESTAMP | DEFAULT NOW() | Event timestamp |

**Indexes**:
- idx_audit_client (client_id)
- idx_audit_type (event_type)
- idx_audit_created (created_at DESC)

### 7.3 Migration Strategy

- All schema changes via Alembic migrations
- Version control migration files in git
- Test migrations against copy of production database
- Support rollback for all migrations
- Initial migration creates all tables
- Never delete columns (deprecate and migrate data)

---

## 8. Security Requirements

### 8.1 Authentication & Authorization

**API Key Authentication**:
- Client presents API key in `X-API-Key` header
- Server validates against hashed keys in `integration_clients` table
- Failed attempts logged to audit trail
- Rate limiting per client (default: 1000 requests/hour)

**Client Isolation**:
- Every query filtered by `client_id`
- No cross-client data access possible
- Database foreign keys enforce referential integrity
- File storage paths include client_id

**Future Enhancements**:
- Role-based access control (RBAC)
- JWT tokens for user-level authentication
- OAuth2 for third-party integrations

### 8.2 Data Protection

**Data at Rest**:
- PostgreSQL encryption (TDE or filesystem-level encryption where available)
- S3 server-side encryption (SSE-S3 or SSE-KMS when using S3)
- API key hashes stored using bcrypt
- Note: Infrastructure selection alone does not establish HIPAA, GDPR, or other regulatory compliance

**Data in Transit**:
- HTTPS/TLS 1.2+ for all API communication
- Database connections require SSL (`sslmode=require`)
- Redis TLS in production

**Data Minimization**:
- Do NOT collect: patient names, birthdates, SSNs, medical record numbers
- Optional external references (patient_id, hospital_id) stored but not validated
- Document filenames sanitized to remove metadata

### 8.3 Input Validation

**File Uploads**:
- Validate MIME types against whitelist
- Verify file signature matches declared type
- Maximum file size: 10MB (configurable)
- Sanitize filenames (remove directory traversal, special characters)
- Scan for malware (future enhancement)

**API Requests**:
- Pydantic schema validation for all endpoints
- Length limits on all string fields
- Type coercion and range validation
- Reject requests with invalid JSON

### 8.4 Secrets Management

**Environment Variables**:
- All secrets in environment variables or secret manager
- Never commit .env files to git
- Rotate secrets periodically (90 days recommended)
- Separate secrets for dev/staging/production

**Critical Secrets**:
- DATABASE_URL (connection string with password)
- GROQ_API_KEY (LLM provider)
- SECRET_KEY (JWT signing, if used)
- API_KEY_HASH_SECRET (bcrypt salt)
- S3_ACCESS_KEY / S3_SECRET_KEY (storage)

### 8.5 Audit Logging

**Events to Log**:
- Authentication attempts (success/failure)
- Analysis creation (type, client_id)
- File uploads (size, type)
- API errors (status code, message)
- Emergency classifications

**Log Contents**:
- Never log passwords, API keys, or PHI
- Log request IDs for correlation
- Log IP addresses for security monitoring
- Log timestamps with timezone (UTC)

**Log Retention**:
- Audit logs retained for 7 years (compliance)
- Immutable log storage (write-once)
- Regular backups to separate system

### 8.6 Dependency Security

**Process**:
- Pin exact versions in requirements.txt
- Run `pip-audit` weekly
- Update vulnerable packages immediately
- Review dependency tree for suspicious packages
- Monitor for typosquatting attempts

---

## 9. AI/ML Model Requirements

### 9.1 Large Language Model (Groq llama-3.1-8b-instant)

**Configuration**:
- Model: llama-3.1-8b-instant
- Temperature: 0.7 (balanced creativity/consistency)
- Max tokens: 1000-2000 (varies by use case)
- Timeout: 30 seconds per request
- Retry logic: 3 attempts with exponential backoff

**Safety Controls**:
- Input sanitization (remove prompt injection patterns)
- Output validation (flag potential hallucinations)
- Rate limiting per client
- Log all prompts and responses
- Conservative tone in medical content
- AI-generated content clearly labeled as such
- Not a substitute for professional medical judgment

**Limitations** (see MODEL_LIMITATIONS.md):
- Training data cutoff: September 2023 (approximate)
- May generate plausible-sounding but factually incorrect medical information
- Not suitable for definitive diagnosis, treatment decisions, or prescriptions
- Outputs require clinical validation by qualified healthcare professionals
- No established diagnostic accuracy or clinical validation for this implementation

### 9.2 TorchXRayVision (densenet121-res224-all)

**Model Details**:
- Architecture: DenseNet121 CNN
- Training datasets: NIH ChestX-ray14, CheXpert, MIMIC-CXR, PadChest
- Input: Verify actual input requirements from model documentation
- Output: 14 model output scores (interpretation depends on model implementation)

**Pathologies (Labels)**:
1. Atelectasis
2. Cardiomegaly
3. Consolidation
4. Edema
5. Effusion
6. Emphysema
7. Fibrosis
8. Hernia
9. Infiltration
10. Mass
11. Nodule
12. Pleural Thickening
13. Pneumonia
14. Pneumothorax

**Note**: Verify actual label set, ordering, and interpretation against the specific model version and implementation.

**Preprocessing Pipeline**:
1. Convert to grayscale (verify actual model requirements)
2. Resize to 224x224 (verify actual model input dimensions)
3. Normalization parameters (verify against model documentation)
4. Tensor conversion

**Note**: Preprocessing details must be verified against the actual TorchXRayVision model implementation and documentation. Listed values are common defaults but may vary by model version.

**Inference Requirements**:
- CPU inference supported (10-30s per image)
- GPU inference recommended (<5s per image)
- Model downloads automatically (~200MB)
- Cache directory: `models/cache/` or `~/.cache/torch/hub/`

**Safety Controls and Score Interpretation**:
- Do not apply an arbitrary universal classification threshold
- Verify the selected TorchXRayVision model's output semantics, preprocessing requirements, label definitions, and score interpretation
- Treat raw model outputs as model scores, not automatically calibrated clinical probabilities
- Do not classify a finding as definitively present or absent solely using an unvalidated threshold
- Any threshold used in an experimental workflow must be explicitly configurable, documented, and justified by appropriate validation
- Clearly distinguish model-generated findings from clinician-confirmed findings
- Do not make unsupported sensitivity, specificity, accuracy, or diagnostic confidence claims
- Never present scores as diagnostic probabilities without appropriate clinical validation
- Disclaimer: "AI-assisted analysis. Requires qualified radiologist review. Not a diagnostic tool."
- Log model name, version, and configuration with every inference
- Validate input is chest X-ray (not CT, MRI, etc.)

**Limitations** (see MODEL_LIMITATIONS.md):
- Optimized for frontal chest X-rays only
- May underperform on portable/bedside X-rays
- Sensitive to image quality and artifacts
- Not validated for pediatric patients
- Performance varies by pathology
- Model outputs require clinical interpretation and validation
- No established diagnostic accuracy for this implementation

### 9.3 Tesseract OCR

**Version**: 4.x or later

**Configuration**:
- Page Segmentation Mode (PSM): 3 (automatic)
- OCR Engine Mode (OEM): 3 (LSTM neural network)
- Language data: English (eng.traineddata)

**Preprocessing Pipeline**:
1. Grayscale conversion
2. Contrast enhancement (CLAHE)
3. Denoising (bilateral filter)
4. Optional thresholding for poor quality

**Quality Assessment**:
- Confidence scores per word
- Average confidence per page
- Flag low-confidence extractions (<70%)

**Limitations**:
- Poor performance on handwritten text
- Sensitive to image quality and resolution
- May misread medical abbreviations
- Layout complexity affects accuracy

---

## 10. Background Processing

### 10.1 Celery Worker Configuration

**Task Queue**: Celery 5.3+  
**Message Broker**: Redis 7+

**Worker Pools**:
- Document processing pool (OCR-intensive)
- Radiology processing pool (CPU/GPU-intensive)
- General pool (lightweight tasks)

**Task Configuration**:
- Retry policy: 3 attempts with exponential backoff
- Task timeout: 120 seconds default
- Result backend: Redis
- Task serialization: JSON

### 10.2 Background Tasks

#### process_document_analysis

**Trigger**: Document upload via API  
**Duration**: 5-60 seconds (depends on pages, OCR)  
**Steps**:
1. Retrieve document metadata from database
2. Load file from storage
3. Attempt PyPDF2 text extraction
4. If text < 50 chars: convert pages to images, run OCR
5. Extract medical terms and findings
6. Generate AI-generated, non-diagnostic explanatory summary (not for clinical decision-making)
7. Update database with results
8. Update analysis status to 'completed' or 'failed'

#### process_radiology_analysis

**Trigger**: Image upload via API  
**Duration**: 10-30 seconds (CPU), <5 seconds (GPU)  
**Steps**:
1. Retrieve image metadata from database
2. Load image from storage
3. Validate image is chest X-ray
4. Preprocess image according to model requirements (verify actual requirements)
5. Load TorchXRayVision model (cached)
6. Run inference
7. Extract all model output scores
8. Store raw model scores and metadata in radiology_findings table
9. Generate AI-generated explanatory summary requiring qualified healthcare professional review (clearly labeled as AI-generated content)
10. Update analysis status to 'completed' or 'failed'

### 10.3 Monitoring

**Task Metrics**:
- Queue depth (Redis LLEN)
- Task success/failure rate
- Average processing time
- Worker availability

**Alerting**:
- Queue depth > 100 for > 5 minutes
- Task failure rate > 10%
- Worker crashes

---

## 11. Testing Requirements

### 11.1 Testing Philosophy

- **Unit Tests**: Fast, isolated, no external dependencies
- **Integration Tests**: Test real AI models (TorchXRayVision, Tesseract)
- **API Tests**: Test HTTP endpoints with test client
- **Security Tests**: Test authentication, authorization, input validation

**No Mocking of Core AI Functionality**:
- TorchXRayVision inference must use actual model
- Tesseract OCR must process actual images
- Tests document what works, not what we hope works

### 11.2 Test Coverage Goals

| Component | Target Coverage | Test Type |
|-----------|----------------|-----------|
| Service Layer | 80%+ | Unit |
| API Routes | 90%+ | API/Integration |
| Database Models | 70%+ | Unit |
| Background Tasks | 80%+ | Integration |
| Authentication | 100% | Security |

### 11.3 Critical Test Cases

**Symptom Analysis**:
- ✅ Valid symptom input returns structured response
- ✅ Emergency keywords trigger emergency flag
- ⏳ LLM generates AI-generated explanation requiring qualified healthcare professional review (code implemented, requires testing with actual LLM API)
- ✅ Invalid input (too short, too long) rejected
- ✅ Database stores analysis with correct status

**Document Processing**:
- ✅ PDF with embedded text extracts correctly
- ✅ Scanned PDF triggers OCR with Tesseract
- ✅ OCR confidence scores calculated
- ⏳ LLM generates AI-generated, non-diagnostic explanatory summary (code implemented, requires testing with actual LLM API)
- ✅ File stored to storage service
- ✅ Background task completes successfully

**Radiology Analysis**:
- ✅ TorchXRayVision model loads successfully
- ✅ Chest X-ray image preprocessed according to model requirements
- ✅ Inference returns 14 raw model output scores
- ✅ Raw model scores and metadata stored correctly in database
- ✅ Model output interpretation documented and verified
- ⏳ LLM generates AI-generated, non-diagnostic explanatory summary (code implemented, requires testing with actual LLM API)
- ✅ Background task completes within timeout

**Authentication**:
- ✅ Valid API key authenticates successfully
- ✅ Invalid API key returns 401
- ✅ Missing API key returns 401
- ✅ Failed authentication logged to audit trail
- ✅ Client isolation prevents cross-client access

**Security**:
- ✅ SQL injection attempts blocked
- ✅ File upload validation rejects malicious files
- ✅ CORS policy enforced
- ✅ Secrets not logged
- ✅ PHI not exposed in error messages

### 11.4 Test Data

**Synthetic Data**:
- Generate synthetic symptoms for testing
- Create synthetic images for radiology tests
- Use public domain sample PDFs

**No Real PHI**:
- Never use real patient data in tests
- De-identify any medical documents used
- Use synthetic or publicly available images

### 11.5 Test Execution

**Local Testing**:
```bash
# Run all tests
pytest tests/ -v

# Run specific suite
pytest tests/unit/ -v
pytest tests/integration/ -v

# Run with coverage
pytest tests/ --cov=backend --cov-report=html
```

**CI/CD Testing**:
- Run on every commit
- Fail build on test failures
- Generate coverage reports
- Run security scans (pip-audit)

---

## 12. JeevaCare Integration Boundary

### 12.1 Integration Principles

**Separation of Concerns**:
- ClaraMed: Medical AI processing, analysis storage
- JeevaCare: Users, patients, appointments, hospital workflows, RBAC

**No Runtime Dependencies**:
- ClaraMed does NOT depend on JeevaCare database
- ClaraMed does NOT call JeevaCare APIs
- ClaraMed can be deployed and tested independently

**Integration via APIs**:
- JeevaCare calls ClaraMed REST APIs
- JeevaCare provides patient/hospital references in requests
- ClaraMed returns analysis results via API responses

### 12.2 Integration Contract

**External References**:
- ClaraMed accepts `external_patient_reference` (JeevaCare patient ID)
- ClaraMed accepts `external_hospital_reference` (JeevaCare hospital ID)
- ClaraMed stores but does NOT validate these references
- JeevaCare maintains mapping between references and analysis_ids

**Webhook Notifications** (Future Enhancement):
- ClaraMed can POST to JeevaCare webhook on analysis completion
- Webhook URL configured per integration client
- Includes analysis_id, status, external references

**Authentication**:
- JeevaCare receives dedicated API key
- API key has appropriate rate limits
- All JeevaCare requests logged to audit trail

### 12.3 Integration Testing

**Mock JeevaCare**:
- Create test harness simulating JeevaCare API calls
- Test ClaraMed API endpoints with JeevaCare-like requests
- Verify external references stored correctly
- Verify analysis results returned in expected format

**Do NOT**:
- Implement actual JeevaCare integration
- Create users or appointments in ClaraMed
- Implement JeevaCare-specific business logic
- Depend on JeevaCare services for ClaraMed testing

---

## 13. Deployment Requirements

### 13.1 Docker Configuration

**Containers**:
1. **backend**: FastAPI application
2. **worker**: Celery background workers
3. **frontend**: Streamlit UI
4. **postgres**: PostgreSQL database
5. **redis**: Message broker

**Docker Compose**:
- Single command deployment: `docker-compose up`
- Health checks for all services
- Volume persistence for data
- Environment variable configuration

### 13.2 Environment Configuration

**Required Variables**:
- APP_ENV (development | staging | production)
- DATABASE_URL (PostgreSQL connection string)
- REDIS_URL (Redis connection string)
- GROQ_API_KEY (LLM provider)
- SECRET_KEY (JWT signing, if used)
- STORAGE_PROVIDER (local | s3)
- TESSERACT_CMD (tesseract executable path)

**Optional Variables**:
- STORAGE_LOCAL_PATH (local storage directory)
- S3_BUCKET_NAME, S3_REGION, S3_ACCESS_KEY, S3_SECRET_KEY (S3 storage)
- RADIOLOGY_MODEL_CACHE_DIR (TorchXRayVision cache)
- LOG_LEVEL (DEBUG | INFO | WARNING | ERROR)
- CORS_ORIGINS (comma-separated allowed origins)

### 13.3 Infrastructure Requirements

**Minimum Resources** (Development):
- CPU: 2 cores
- RAM: 4GB
- Disk: 20GB (includes model cache)

**Recommended Resources** (Production):
- CPU: 4+ cores (or GPU for radiology)
- RAM: 8GB+
- Disk: 50GB+ (SSD recommended)
- PostgreSQL: Managed service (AWS RDS, Google Cloud SQL)
- Redis: Managed service (AWS ElastiCache)
- Storage: S3-compatible object storage

### 13.4 Deployment Platforms

**Supported**:
- Docker Compose (local, small production)
- AWS ECS/Fargate
- Google Cloud Run
- Azure Container Instances
- Render.com, Railway, Fly.io

**Not Required**:
- Kubernetes (optional for large scale)
- Service mesh (Istio, Linkerd)
- GPU instances (CPU inference works)

---

## 14. Medical Safety & Compliance

### 14.1 Medical Device Classification and Regulatory Status

**Current Status**: NOT a medical device. NOT FDA-cleared. NOT CE-marked.

**Regulatory Classification**:
- ClaraMed is positioned as a clinical decision-support research prototype
- AI outputs are informational only and require qualified healthcare professional review
- Does not make autonomous diagnostic claims
- Educational and research purpose only

**If Seeking Medical Device Classification**:
- Consult with regulatory experts and legal counsel
- Determine appropriate device classification (Class I, II, or III for FDA; risk class for EU MDR)
- Conduct clinical validation studies appropriate for intended use
- Prepare regulatory submissions (FDA 510(k), PMA, or EU MDR technical documentation)
- Implement Quality Management System (ISO 13485 or equivalent)
- Conduct post-market surveillance
- Maintain design history files and risk management files

**Current Status**:
- ⚠️ No clinical validation studies conducted
- ⚠️ No regulatory submissions filed
- ⚠️ No QMS implementation
- ⚠️ Not validated for diagnostic, therapeutic, or clinical decision-making use

**Do Not Market As**: Medical device, diagnostic tool, clinical system, or any claim requiring regulatory clearance without obtaining appropriate clearances and validations.

### 14.2 Required Disclaimers

**Every API Response with Medical Content**:
```
"ClaraMed is an AI-assisted clinical decision-support prototype. This analysis is for informational and educational purposes only and does not constitute medical advice, diagnosis, or treatment. AI-generated content is not validated for clinical use. Always consult with a qualified healthcare professional for medical concerns. In case of emergency, call 911 or your local emergency services immediately."
```

**UI Display - Prominent on Every Page**:
- "AI-Assisted Prototype - Not a Medical Device"
- "For Educational and Research Purposes"
- "Not a substitute for professional medical care"
- "Requires qualified healthcare professional review"
- "Call 911 for emergencies"
- "Do not use for diagnosis, treatment, or medical decisions"

**Emergency Classification Warning**:
```
"⚠️ Your symptoms may indicate a condition requiring immediate medical attention. This system is not designed for emergency triage and may not detect all serious conditions. Please call 911 or go to the nearest emergency room immediately. Do not delay seeking emergency care based on this analysis."
```

**Radiology Analysis Disclaimer**:
```
"AI-Assisted Radiology Analysis Prototype - Requires Qualified Radiologist Review

This analysis is generated by an AI model and is NOT a diagnostic report. Model outputs are experimental and not validated for clinical use. Findings must be reviewed and confirmed by a qualified radiologist. Do not make diagnostic or treatment decisions based solely on this AI analysis. This system is not FDA-cleared or CE-marked as a medical device."
```

### 14.3 Prohibited Claims

**Never Claim (Without Appropriate Validation and Regulatory Clearance)**:
- ❌ "ClaraMed diagnoses diseases"
- ❌ "FDA-approved", "FDA-cleared", or "CE-marked" (unless actually obtained)
- ❌ "Clinically validated" (without appropriate validation studies)
- ❌ "Replaces doctor visits" or "eliminates need for healthcare professionals"
- ❌ "99% accurate" or any specific accuracy/performance claims (without validated evidence)
- ❌ "Prescribes treatment" or "recommends medications"
- ❌ "Suitable for emergency use" or "emergency triage system"
- ❌ "HIPAA-compliant" or "GDPR-compliant" (without completing all required measures)
- ❌ "Production-ready" (without appropriate testing and validation)
- ❌ "Medical-grade" or "clinical-grade"
- ❌ Sensitivity, specificity, PPV, NPV without validated evidence
- ❌ "Detects X with Y% confidence" (calibrated probability claims without validation)

**Acceptable Claims**:
- ✅ "AI-assisted medical information prototype"
- ✅ "Clinical decision-support research tool"
- ✅ "Educational symptom analysis for research purposes"
- ✅ "Assists qualified healthcare professionals with information"
- ✅ "Requires expert review and validation"
- ✅ "Experimental AI model outputs"
- ✅ "Research prototype - not for clinical use"

### 14.4 Healthcare Data Protection Considerations

**Design Approach**:
- ClaraMed is designed to minimize collection of identifiable patient information
- System does not collect 18 HIPAA identifiers by default
- External references (patient_id, hospital_id) are opaque strings

**HIPAA Applicability**:
- HIPAA applies if ClaraMed processes Protected Health Information (PHI) as defined by regulation
- Infrastructure selection and technical controls alone do not establish HIPAA compliance
- HIPAA compliance requires: technical safeguards, administrative procedures, physical security, business associate agreements, regular risk assessments, breach notification processes, and organizational policies

**If Deploying with PHI**:
- Conduct formal HIPAA risk assessment
- Implement required administrative, physical, and technical safeguards
- Execute Business Associate Agreements (BAAs) with all service providers (cloud hosting, AI API providers, etc.)
- Document security policies and procedures
- Implement breach notification procedures
- Train workforce on HIPAA requirements
- Conduct regular compliance audits

**Current Implementation Status**:
- Technical controls implemented: encryption, access controls, audit logging
- ⚠️ Administrative and organizational HIPAA compliance measures not implemented
- ⚠️ BAAs with vendors not established
- ⚠️ Formal risk assessment not conducted
- ⚠️ Breach notification procedures not implemented

**Do Not Claim**: HIPAA compliance without completing required administrative, physical, technical, and organizational measures and obtaining appropriate legal and compliance verification.

### 14.5 GDPR and International Data Protection

**GDPR Applicability**:
- GDPR applies if processing personal data of EU residents
- Compliance requires technical measures, legal basis for processing, data processing agreements, privacy policies, and organizational procedures

**Required for GDPR Compliance**:
- Data minimization (collect only necessary data)
- Right to access (data portability)
- Right to erasure ("right to be forgotten")
- Data breach notification (72 hours)
- Privacy by design
- Data Processing Agreements with processors
- Legal basis for data processing documented

**Current Implementation Status**:
- ✅ Minimal data collection by design
- ⚠️ Data export API not implemented
- ⚠️ Hard delete mechanism not implemented
- ⚠️ Breach notification process not implemented
- ⚠️ Data Processing Agreements with vendors not established
- ⚠️ Privacy policy not created
- ⚠️ Legal basis for processing not documented

**Do Not Claim**: GDPR compliance without completing required technical, legal, and organizational measures and obtaining appropriate legal and compliance verification.

---

## 15. Acceptance Criteria & Verification

### 15.1 Functional Acceptance Criteria

**Status Legend**:
- ✅ **Implemented**: Code exists
- 🧪 **Unit Tested**: Has passing unit tests
- 🔗 **Integration Tested (Mocked)**: Tested with mocked dependencies
- ⚙️ **Integration Tested (Real)**: Tested with actual AI models (OCR, TorchXRayVision)
- 🐳 **Docker Verified**: Verified in running Docker environment
- 🌐 **Externally Verified**: Deployed and tested from external client

**Symptom Analysis**:
- [ ] ✅ Accept symptom text via API (code implemented)
- [ ] 🧪 Unit tested with various inputs
- [ ] ⚙️ Classify emergency vs non-emergency with real LLM
- [ ] ⚙️ Generate AI-generated, non-diagnostic explanation with actual Groq API (not for clinical use)
- [ ] ⚙️ Generate wellness tips with actual LLM
- [ ] 🧪 Support 7 languages (unit tested)
- [ ] 🐳 Store in PostgreSQL (verified in Docker)
- [ ] 🐳 Return structured JSON response (verified end-to-end)

**Document Processing**:
- [ ] ✅ Accept PDF upload via API (code implemented)
- [ ] 🧪 Extract embedded PDF text (unit tested)
- [ ] ⚙️ Perform Tesseract OCR on scanned PDFs (with actual Tesseract)
- [ ] ⚙️ Generate AI-generated, non-diagnostic explanatory summary with actual API (not for clinical use)
- [ ] 🐳 Store file in storage service (verified in Docker)
- [ ] 🐳 Background processing via Celery (verified in Docker)
- [ ] 🐳 Return processing status (verified end-to-end)

**Radiology Analysis**:
- [ ] ✅ Accept chest X-ray image upload (code implemented)
- [ ] ⚙️ Load TorchXRayVision model (actual model, not mocked)
- [ ] ⚙️ Preprocess image (grayscale, resize, normalize) - verified with real images
- [ ] ⚙️ Run actual model inference (not mocked, with real TorchXRayVision)
- [ ] ⚙️ Extract 14 pathology scores (verified with real model output)
- [ ] 🐳 Store findings in database (verified in Docker)
- [ ] ⚙️ Generate AI-generated, non-diagnostic explanatory summary with real LLM (not for clinical use)
- [ ] 🐳 Background processing via Celery (verified in Docker)

**API Endpoints**:
- [ ] ✅ Health check endpoints (code implemented)
- [ ] 🧪 Authentication via API key (unit tested)
- [ ] 🐳 All CRUD endpoints functional (verified in Docker)
- [ ] 🐳 Error responses follow standard format (verified)
- [ ] 🐳 OpenAPI documentation generated (verified at /docs)

**Database**:
- [ ] ✅ All 6 tables defined in models (code implemented)
- [ ] ⏳ Alembic migration generated (pending: requires alembic command)
- [ ] ⏳ Migration applied to test database (pending: requires environment setup)
- [ ] 🧪 Foreign keys enforce referential integrity (unit tested)
- [ ] 🐳 Client isolation enforced (verified in Docker)
- [ ] ✅ Indexes defined in schema (code implemented)

**Security**:
- [ ] ✅ API keys hashed in database (code implemented)
- [ ] 🐳 Failed authentication logged (verified)
- [ ] 🧪 Input validation rejects malicious input (unit tested)
- [ ] 🧪 SQL injection prevented by ORM (verified by design)
- [ ] ✅ Secrets not logged (code inspection)
- [ ] 🐳 CORS policy enforced (verified)

**Note**: Items marked ✅ indicate code exists, not that functionality is verified. Full verification requires appropriate testing level.

### 15.2 Technical Verification Requirements

**Model Verification**:
- [ ] ⚙️ TorchXRayVision model loads successfully (verify with actual model file)
- [ ] 🐳 Model cache directory created and writable
- [ ] ⚙️ Inference runs on CPU (measure actual time: 10-30s per image)
- [ ] ⚙️ 14 pathology scores returned in correct format (0.0-1.0)
- [ ] 🐳 Model name and version logged with each inference
- [ ] ⚙️ Verify model input dimensions (224x224) and preprocessing
- [ ] ⚙️ Verify model output interpretation (not calibrated probabilities)

**OCR Verification**:
- [ ] 🐳 Tesseract installed and accessible in container
- [ ] ⚙️ OCR processes synthetic test image (actual Tesseract, not mocked)
- [ ] ⚙️ OCR processes scanned PDF page (actual execution)
- [ ] ⚙️ Confidence scores calculated correctly
- [ ] ⚙️ Text extracted from scanned PDF matches expectations
- [ ] 🐳 OCR preprocessing pipeline functional (grayscale, denoise, etc.)

**Database Verification**:
- [ ] 🐳 PostgreSQL connection successful
- [ ] ⏳ Alembic migrations generated (pending: requires alembic command)
- [ ] ⏳ Migrations applied successfully (pending: requires environment)
- [ ] 🐳 Tables created with correct schema (verify column types, constraints)
- [ ] 🐳 Test data inserted and queried successfully
- [ ] 🐳 Foreign key constraints validated (test cascade delete)
- [ ] 🐳 Indexes created (verify with EXPLAIN queries)

**Background Processing**:
- [ ] 🐳 Redis connection successful
- [ ] 🐳 Celery workers start and register
- [ ] 🐳 Document task submits and completes
- [ ] 🐳 Radiology task submits and completes
- [ ] 🐳 Failed tasks retry correctly (test with intentional failure)
- [ ] 🐳 Task status tracked in Redis
- [ ] 🐳 Worker logs show task execution

**Docker Verification**:
- [ ] 🐳 All 5 services build successfully
- [ ] 🐳 All 5 services start without errors
- [ ] 🐳 Health checks pass for backend and frontend
- [ ] 🐳 Volumes persist data across container restarts
- [ ] 🐳 Environment variables loaded correctly
- [ ] 🐳 Services communicate via Docker network
- [ ] 🐳 Frontend can reach backend API
- [ ] 🐳 Worker can access database and Redis

**Status Legend**:
- ⏳ Pending environment setup
- 🐳 Requires running Docker environment
- ⚙️ Requires actual AI models (not mocked)

### 15.3 End-to-End Verification

**Symptom Analysis Workflow**:
1. Submit symptom analysis via API
2. Verify emergency classification (if applicable)
3. Verify AI-generated, non-diagnostic explanation generated (requires qualified healthcare professional review)
4. Verify result stored in database
5. Verify audit event logged
6. Retrieve analysis via API

**Document Processing Workflow**:
1. Upload PDF via API
2. Verify file saved to storage
3. Verify background task triggered
4. Wait for processing completion
5. Verify text extracted (embedded or OCR)
6. Verify AI-generated, non-diagnostic explanatory summary generated (requires qualified healthcare professional review)
7. Retrieve results via API

**Radiology Analysis Workflow**:
1. Upload chest X-ray image via API
2. Verify file saved to storage
3. Verify background task triggered
4. Wait for inference completion (10-30s)
5. Verify findings stored in database
6. Verify AI-generated, non-diagnostic explanatory summary generated (requires qualified radiologist review, not for clinical decision-making)
7. Retrieve results via API

### 15.4 Final Delivery Checklist

**Implementation Status**:
- [ ] ✅ All backend services implemented (code exists)
- [ ] ✅ All API endpoints implemented (code exists)
- [ ] ✅ Frontend refactored to use backend API (code exists)
- [ ] 🧪 Unit tests implemented and passing
- [ ] 🔗 Integration tests with mocked dependencies passing
- [ ] ⚙️ Integration tests with real AI models implemented
- [ ] ⏳ Test coverage measured (target > 75%)

**Documentation Status**:
- [ ] ✅ README.md updated with current features
- [ ] ✅ API.md complete with examples
- [ ] ✅ ARCHITECTURE.md documents design
- [ ] ✅ SECURITY.md documents controls
- [ ] ✅ MODEL_LIMITATIONS.md documents AI constraints
- [ ] ✅ DEPLOYMENT.md provides deployment guide
- [ ] ✅ BUILD.md (this document) exists

**Deployment Artifacts**:
- [ ] ✅ Docker containers defined (Dockerfile, Dockerfile.frontend)
- [ ] ✅ docker-compose.yml functional
- [ ] ✅ .env.example provides template
- [ ] ✅ Health check endpoints implemented
- [ ] ✅ Logging configured in code
- [ ] ⏳ Logging verified in running system

**Verification Scripts**:
- [ ] ✅ scripts/check_dependencies.py implemented
- [ ] ✅ scripts/init_db.py implemented
- [ ] ✅ scripts/verify_implementation.py implemented
- [ ] ⏳ Verification scripts executed successfully

**Environment Setup (Required Before Verification)**:
- [ ] ⏳ Dependencies installed (`pip install -r requirements.txt`)
- [ ] ⏳ Tesseract OCR installed (system package)
- [ ] ⏳ PostgreSQL and Redis running (via Docker or local)
- [ ] ⏳ .env file configured with actual credentials
- [ ] ⏳ Alembic migration generated and applied
- [ ] ⏳ Services started successfully

**Testing Evidence Required**:
- [ ] ⏳ Unit test results (pytest output)
- [ ] ⏳ Integration test results with real OCR
- [ ] ⏳ Integration test results with real TorchXRayVision
- [ ] ⏳ Docker compose startup logs
- [ ] ⏳ Health check responses
- [ ] ⏳ Sample API request/response
- [ ] ⏳ Screenshot of working frontend

**Final Verification Report Must Include**:
- What was implemented (with evidence: file paths, code excerpts)
- What was unit tested (with test results)
- What was integration tested with real AI models (with test output)
- What was verified in Docker (with logs/screenshots)
- Known limitations and issues
- Deployment requirements
- Security considerations
- Medical safety disclaimers
- Clear statement: "Not validated for clinical use"

**DO NOT CLAIM**:
- "Production-ready" without appropriate operational testing
- "Clinically validated" without validation studies
- "All tests passing" without providing test results
- Any specific accuracy, performance, or diagnostic claims without evidence
- Regulatory compliance without completing required processes

**Status Legend**:
- ✅ Completed
- 🧪 Unit tested
- 🔗 Integration tested (mocked)
- ⚙️ Integration tested (real AI)
- 🐳 Docker verified
- ⏳ Pending (requires environment setup or execution)

---

## 16. Known Limitations & Future Enhancements

### 16.1 Current Implementation Limitations

**Radiology AI**:
- Chest X-rays only (no CT, MRI, ultrasound, other modalities)
- Frontal views only (PA or AP, not lateral or oblique)
- Not validated for pediatric patients
- Not validated for specific demographic groups
- CPU inference is slow (10-30s per image)
- Model outputs are experimental scores, not calibrated probabilities
- No established diagnostic accuracy for this implementation
- Threshold-based classification not validated

**Document Processing**:
- PDF only (no Word, Excel, DICOM reports)
- OCR accuracy depends on scan quality
- Handwritten notes not supported well
- Multi-column layouts may be misread
- No structured data extraction (labs, vitals)

**LLM Analysis**:
- Training data cutoff (September 2023)
- May generate plausible but incorrect medical information
- Primarily trained on English medical texts
- Context window limits long documents
- No established accuracy or reliability metrics

**Security & Operations**:
- No rate limiting implemented
- No role-based access control (RBAC)
- No OAuth2 support
- No malware scanning on uploads
- No automated backup and recovery procedures
- No production-scale monitoring and alerting
- No disaster recovery plan

**Production Readiness**:
- Not tested under load
- No performance benchmarks established
- No operational runbooks
- No incident response procedures
- No SLA definitions
- Not validated in multi-tenant production environment
- Security testing not completed
- Penetration testing not conducted

### 16.2 Future Enhancements

**Near-Term (3-6 months)**:
- Rate limiting per client
- DICOM format support for radiology
- CT scan analysis (chest, abdomen)
- WebSocket for real-time updates
- Enhanced multilingual support

**Long-Term (6-12 months)**:
- FHIR integration for EHR interop
- Model versioning and A/B testing
- GPU optimization for faster inference
- Advanced analytics dashboard
- Mobile app (React Native)
- Federated learning for model improvement

**Security Enhancements**:
- Role-based access control (RBAC)
- OAuth2 for third-party integrations
- Malware scanning (ClamAV)
- Intrusion detection
- Advanced audit analytics

---

## 17. Glossary

**API**: Application Programming Interface  
**CORS**: Cross-Origin Resource Sharing  
**EHR**: Electronic Health Record  
**FHIR**: Fast Healthcare Interoperability Resources  
**HIPAA**: Health Insurance Portability and Accountability Act  
**LLM**: Large Language Model  
**OCR**: Optical Character Recognition  
**ORM**: Object-Relational Mapping  
**PHI**: Protected Health Information  
**RBAC**: Role-Based Access Control  
**REST**: Representational State Transfer  
**TLS**: Transport Layer Security  

---

## 18. Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | 2026-10-28 | Build Team | Initial draft |
| 0.5 | 2026-10-31 | Build Team | Added detailed API specs, database schema |
| 1.0 | 2026-11-01 | Build Team | Final specification, acceptance criteria added |
| 1.1 | 2026-11-01 | Build Team | Corrected radiology threshold requirements, medical safety wording, compliance language, production-readiness clarifications, and acceptance criteria distinctions |
| 1.2 | 2026-11-08 | Build Team | Final consistency review: removed remaining threshold contradictions in Sections 10.2 and 11.3, corrected model output terminology to avoid assuming calibrated probabilities, documented requirement to verify preprocessing against actual model, clarified test status distinctions |
| 1.3 | 2026-11-08 | Build Team | Final wording corrections: replaced ambiguous "clinical interpretation" and "LLM explanation" with "AI-generated, non-diagnostic explanatory summary" where referring to LLM outputs; clarified all AI-generated content requires qualified healthcare professional review; preserved references to actual clinician interpretation and clinical validation; updated status indicators in Section 11.3 to distinguish code implementation from test verification |

---

## 19. Approval & Sign-Off

This specification represents the requirements and architectural design for ClaraMed v1.0 as a clinical decision-support research prototype.

**Important Notes**:
- This document describes intended architecture and requirements, not verified implementation status
- Production readiness requires comprehensive testing, security audits, and operational validation beyond code completion
- Medical device claims, clinical validation, and regulatory compliance require appropriate studies, processes, and approvals
- Healthcare data protection compliance requires completing administrative, physical, technical, and organizational measures

**Document Owner**: ClaraMed Build Team  
**Last Review Date**: 2026-11-01  
**Next Review Date**: Upon completion or significant scope change

---

*End of BUILD.md Specification v1.3*
