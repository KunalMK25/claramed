# ClaraMed Architecture

## Overview

ClaraMed is a production-grade AI-powered medical analysis platform built on a modern, scalable architecture with clear separation of concerns, asynchronous processing, and extensible AI capabilities.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  Streamlit   │  │  Mobile App  │  │  Third-Party │         │
│  │   Frontend   │  │   (Future)   │  │     APIs     │         │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │
└─────────┼──────────────────┼──────────────────┼─────────────────┘
          │                  │                  │
          └──────────────────┴──────────────────┘
                             │
          ┌──────────────────▼──────────────────┐
          │         API Gateway Layer           │
          │  ┌────────────────────────────┐    │
          │  │   FastAPI Application      │    │
          │  │  - CORS Middleware         │    │
          │  │  - Auth Middleware         │    │
          │  │  - Error Handling          │    │
          │  │  - Request Validation      │    │
          │  └────────────┬───────────────┘    │
          └───────────────┼─────────────────────┘
                          │
          ┌───────────────┴───────────────┐
          │                               │
┌─────────▼──────────┐         ┌─────────▼──────────┐
│   Service Layer    │         │  Background Jobs   │
│                    │         │                    │
│  ┌──────────────┐ │         │  ┌──────────────┐ │
│  │   Symptom    │ │         │  │    Celery    │ │
│  │   Analysis   │ │         │  │    Workers   │ │
│  └──────────────┘ │         │  └──────┬───────┘ │
│  ┌──────────────┐ │         │         │         │
│  │  Emergency   │ │         │  ┌──────▼───────┐ │
│  │ Detection    │ │         │  │ Document OCR │ │
│  └──────────────┘ │         │  │  Processing  │ │
│  ┌──────────────┐ │         │  └──────────────┘ │
│  │  Document    │ │         │  ┌──────────────┐ │
│  │  Processing  │ │         │  │  Radiology   │ │
│  └──────────────┘ │         │  │  Inference   │ │
│  ┌──────────────┐ │         │  └──────────────┘ │
│  │  Radiology   │ │         └────────────────────┘
│  │  Analysis    │ │                  │
│  └──────────────┘ │                  │
│  ┌──────────────┐ │         ┌────────▼─────────┐
│  │   Storage    │ │────────▶│  Redis Message   │
│  │   Service    │ │         │      Broker      │
│  └──────────────┘ │         └──────────────────┘
└────────┬───────────┘
         │
┌────────▼──────────────────────────────────────┐
│            Data Layer                         │
│  ┌──────────────┐  ┌────────────────────┐   │
│  │  PostgreSQL  │  │  File Storage      │   │
│  │   Database   │  │  (Local / S3)      │   │
│  │              │  │                    │   │
│  │  - Analyses  │  │  - Documents       │   │
│  │  - Results   │  │  - Images          │   │
│  │  - Documents │  │  - Reports         │   │
│  │  - Findings  │  │                    │   │
│  │  - Audit Log │  │                    │   │
│  └──────────────┘  └────────────────────┘   │
└───────────────────────────────────────────────┘

┌───────────────────────────────────────────────┐
│          AI/ML Components                     │
│  ┌────────────┐  ┌──────────────────────┐   │
│  │    LLM     │  │  Computer Vision     │   │
│  │  Provider  │  │     Models           │   │
│  │  (Groq)    │  │                      │   │
│  │            │  │  - TorchXRayVision   │   │
│  │  - Symptom │  │  - Image Processing  │   │
│  │    Analysis│  │  - Finding Detection │   │
│  │  - Document│  │                      │   │
│  │    Explain │  │                      │   │
│  └────────────┘  └──────────────────────┘   │
│  ┌────────────┐                             │
│  │    OCR     │                             │
│  │ (Tesseract)│                             │
│  │            │                             │
│  │  - Text    │                             │
│  │    Extract │                             │
│  │  - Language│                             │
│  │    Support │                             │
│  └────────────┘                             │
└───────────────────────────────────────────────┘
```

## Core Components

### 1. API Layer (FastAPI)

**Location**: `backend/main.py`, `backend/api/`

**Responsibilities**:
- HTTP request handling and routing
- Request validation using Pydantic schemas
- Authentication and authorization
- Rate limiting and request throttling
- Error handling and logging
- CORS management
- OpenAPI documentation generation

**Key Features**:
- Async/await support for concurrent request handling
- Dependency injection for database sessions and auth
- Middleware for cross-cutting concerns
- Health check and readiness endpoints

### 2. Service Layer

**Location**: `backend/services/`

**Components**:

#### Symptom Service
- Input validation and sanitization
- Symptom severity classification
- Medical specialty routing
- LLM-powered analysis generation
- Structured result formatting

#### Emergency Detection Service
- Keyword-based initial screening
- LLM-powered context-aware classification
- Severity scoring (1-5 scale)
- Recommended action generation

#### Document Service
- PDF text extraction (PyPDF2)
- Multi-page document handling
- Medical terminology extraction
- LLM-powered document summarization
- Metadata management

#### OCR Service
- Image preprocessing (grayscale, contrast, denoise)
- PDF to image conversion
- Tesseract OCR integration
- Multi-language support
- Confidence scoring
- Text post-processing

#### Radiology Service
- TorchXRayVision model management
- Image preprocessing (resize, normalize)
- Multi-class pathology detection
- Confidence thresholding
- Finding annotation
- Clinical interpretation generation

#### Storage Service
- File upload/download abstraction
- Local filesystem support
- S3-compatible object storage support
- Presigned URL generation
- Automatic cleanup and retention

### 3. Background Processing

**Location**: `backend/workers/`

**Technology**: Celery + Redis

**Tasks**:
- `process_document_analysis`: Async PDF/OCR processing
- `process_radiology_analysis`: Async X-ray inference

**Benefits**:
- Non-blocking API responses
- Resource-intensive task isolation
- Retry mechanisms for transient failures
- Task monitoring and logging
- Horizontal scalability

### 4. Data Layer

#### Database (PostgreSQL)

**Schema**:
- `medical_analyses`: Core analysis records
- `analysis_results`: Structured result data
- `uploaded_documents`: File metadata and references
- `radiology_findings`: X-ray pathology detections
- `integration_clients`: API authentication clients
- `audit_events`: Security and compliance logging

**Features**:
- JSONB columns for flexible data structures
- Foreign key constraints for referential integrity
- Indexes for query performance
- Enum types for controlled vocabularies
- Timestamps for audit trails

#### File Storage

**Modes**:
- **Local**: Development and small deployments
- **S3-Compatible**: Production scalability (AWS S3, MinIO, etc.)

**Organization**:
```
storage/
├── documents/
│   └── {client_id}/{analysis_id}/{filename}
├── images/
│   └── {client_id}/{analysis_id}/{filename}
└── reports/
    └── {client_id}/{analysis_id}/{filename}
```

### 5. AI/ML Components

#### LLM Provider (Groq)

**Model**: llama-3.1-8b-instant

**Uses**:
- Symptom analysis and triage
- Emergency classification
- Document explanation
- Medical terminology interpretation

**Configuration**:
- Temperature: 0.7 (balanced creativity/consistency)
- Max tokens: 1000-2000 (varies by use case)
- Retry logic for API failures
- Response validation

#### Computer Vision (TorchXRayVision)

**Model**: densenet121-res224-all

**Pathologies Detected**:
- Atelectasis
- Cardiomegaly
- Consolidation
- Edema
- Effusion
- Emphysema
- Fibrosis
- Hernia
- Infiltration
- Mass
- Nodule
- Pleural Thickening
- Pneumonia
- Pneumothorax

**Pipeline**:
1. Image loading and validation
2. Preprocessing (resize to 224x224, normalize)
3. Model inference (forward pass)
4. Sigmoid activation for probabilities
5. Threshold filtering (>0.5)
6. Result formatting with confidence scores

#### OCR (Tesseract)

**Version**: 4.x or later

**Configuration**:
- PSM Mode 3: Fully automatic page segmentation
- OEM 3: LSTM neural network engine
- Language data: English (eng.traineddata)

**Preprocessing Pipeline**:
1. Grayscale conversion
2. Contrast enhancement (CLAHE)
3. Denoising (bilateral filter)
4. Optional thresholding for low-quality scans

### 6. Frontend (Streamlit)

**Location**: `app_new.py`, `frontend/`

**Architecture**:
- API-driven (no direct database access)
- Session state management
- Async API client with retries
- Real-time analysis status polling
- Responsive layout with custom CSS

**Features**:
- Interactive body map for symptom selection
- Multi-language support (English, Spanish, French, Chinese, Arabic)
- Visual condition mapping
- Document upload with preview
- Radiology image viewer
- Analysis history browser
- Emergency alert UI

## Data Flow

### Symptom Analysis Flow

```
User Input → FastAPI Endpoint → Symptom Service
                                      ↓
                              Validation & Enrichment
                                      ↓
                              LLM Analysis Request
                                      ↓
                              Result Formatting
                                      ↓
                         Database Storage (PostgreSQL)
                                      ↓
                              JSON Response
```

### Document Analysis Flow

```
File Upload → FastAPI Endpoint → Storage Service
                                      ↓
                              File Saved (Local/S3)
                                      ↓
                              Celery Task Created
                                      ↓
                              Background Worker
                                      ↓
                         PDF Text Extraction / OCR
                                      ↓
                              LLM Explanation
                                      ↓
                         Database Update (Result)
                                      ↓
                         Client Polls Status Endpoint
```

### Radiology Analysis Flow

```
Image Upload → FastAPI Endpoint → Storage Service
                                      ↓
                              File Saved (Local/S3)
                                      ↓
                              Celery Task Created
                                      ↓
                              Background Worker
                                      ↓
                         TorchXRayVision Inference
                                      ↓
                         Finding Detection & Storage
                                      ↓
                         Database Update (Result + Findings)
                                      ↓
                         Client Polls Status Endpoint
```

## Security Architecture

### Authentication & Authorization

- **API Key-based**: X-API-Key header for programmatic access
- **Client Isolation**: All queries filtered by `client_id`
- **Audit Logging**: All operations logged to `audit_events` table

### Data Protection

- **At Rest**: PostgreSQL encryption (filesystem/volume level)
- **In Transit**: HTTPS/TLS for all API communication
- **File Access**: Presigned URLs for temporary access
- **PII Handling**: No storage of identifiable patient data (design assumption)

### Network Security

- **CORS**: Configurable allowed origins
- **Rate Limiting**: Per-client API throttling (future enhancement)
- **Input Validation**: Pydantic schemas enforce strict typing
- **SQL Injection Prevention**: SQLAlchemy ORM parameterization

## Scalability Considerations

### Horizontal Scaling

- **API Servers**: Stateless FastAPI instances behind load balancer
- **Celery Workers**: Independent worker pools for different task types
- **Database**: Read replicas for query distribution
- **Storage**: S3-compatible object storage auto-scales

### Vertical Scaling

- **GPU Acceleration**: TorchXRayVision supports CUDA for faster inference
- **Connection Pooling**: SQLAlchemy manages database connections efficiently
- **Caching**: Redis can cache frequent queries (future enhancement)

### Performance Optimization

- **Async I/O**: FastAPI and async services minimize blocking
- **Background Processing**: CPU-intensive tasks offloaded to workers
- **Database Indexes**: Strategic indexes on query columns
- **File Streaming**: Large files streamed rather than loaded into memory

## Deployment Architecture

### Docker Compose (Development/Small Production)

**Services**:
1. **api**: FastAPI application
2. **frontend**: Streamlit interface
3. **worker**: Celery background workers
4. **db**: PostgreSQL database
5. **redis**: Message broker and cache

**Networking**: Internal Docker network with exposed ports for frontend/API

### Kubernetes (Large Production)

**Components**:
- **Deployments**: API pods, worker pods, frontend pods
- **Services**: Load balancing and service discovery
- **PersistentVolumeClaims**: Database and file storage
- **ConfigMaps/Secrets**: Environment configuration
- **Ingress**: External traffic routing with TLS termination

## Monitoring & Observability

### Logging

- **Structured Logging**: JSON format with contextual fields
- **Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Log Aggregation**: Centralized collection (e.g., ELK stack)

### Metrics

- **API Metrics**: Request count, latency, error rate
- **Worker Metrics**: Task queue depth, processing time, failure rate
- **Database Metrics**: Connection pool usage, query performance
- **Model Metrics**: Inference latency, batch sizes

### Health Checks

- **Liveness**: `/health` endpoint (is service running?)
- **Readiness**: `/health/ready` endpoint (can service handle traffic?)
- **Dependencies**: Database, Redis, storage connectivity checks

## Extensibility

### Adding New Analysis Types

1. Create service in `backend/services/new_service.py`
2. Define Pydantic schemas in `backend/schemas/`
3. Add database models if needed
4. Create API route in `backend/api/routes/`
5. Add background task if long-running
6. Update frontend with new UI components

### Integrating New AI Models

1. Add model loader in appropriate service
2. Implement preprocessing pipeline
3. Add inference method with error handling
4. Create result parsing logic
5. Update database schema for new finding types

### Supporting New Storage Backends

1. Extend `StorageService` abstract methods
2. Implement provider-specific client
3. Add configuration in `.env`
4. Update storage factory in service initialization

## Technology Choices Rationale

| Component | Choice | Rationale |
|-----------|--------|-----------|
| API Framework | FastAPI | Async support, auto-docs, type safety, performance |
| Database | PostgreSQL | JSONB support, reliability, HIPAA-ready managed services |
| Task Queue | Celery + Redis | Mature, battle-tested, excellent monitoring ecosystem |
| ORM | SQLAlchemy | Industry standard, great FastAPI integration, migration support |
| Frontend | Streamlit | Rapid development, Python-native, good for medical dashboards |
| LLM | Groq (llama-3.1) | Fast inference, reasonable cost, good medical reasoning |
| Vision Model | TorchXRayVision | Pretrained on medical data, multi-pathology, active research |
| OCR | Tesseract | Open source, production-ready, multi-language, no API costs |
| Containerization | Docker | Standard, reproducible, easy deployment |

## Future Architecture Considerations

### Planned Enhancements

1. **Caching Layer**: Redis for frequent query results
2. **API Versioning**: `/v1/`, `/v2/` routing for breaking changes
3. **Real-time Updates**: WebSocket for live analysis progress
4. **Model Versioning**: Track and roll back AI model updates
5. **Feature Flags**: Gradual rollout of new capabilities
6. **Multi-tenancy**: Organization-level isolation above clients

### Migration Paths

- **Database**: Alembic migrations for schema evolution
- **API**: Backward-compatible changes, deprecation notices
- **Models**: Shadow deployments, A/B testing
- **Storage**: Background data migration scripts

## Conclusion

ClaraMed's architecture prioritizes:
- **Modularity**: Clear separation of concerns
- **Scalability**: Horizontal and vertical scaling paths
- **Reliability**: Error handling, retries, health checks
- **Security**: Authentication, authorization, audit logging
- **Maintainability**: Type safety, documentation, testing

This foundation supports both current requirements and future growth as a production medical AI platform.
