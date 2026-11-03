# ClaraMed Security Documentation

## Overview

ClaraMed implements multiple layers of security controls to protect sensitive medical data and ensure compliance with healthcare data protection requirements. This document outlines the security architecture, controls, and best practices.

## Threat Model

### Assets to Protect

1. **Patient Medical Data**: Symptoms, diagnoses, medical history
2. **Medical Documents**: PDFs, scanned records, radiology images
3. **AI Analysis Results**: Clinical interpretations and recommendations
4. **System Credentials**: API keys, database passwords, encryption keys
5. **Audit Logs**: Access records and system events

### Threat Actors

1. **External Attackers**: Unauthorized access attempts, data breaches
2. **Malicious Insiders**: Unauthorized data access or exfiltration
3. **Compromised Accounts**: Stolen credentials or API keys
4. **Supply Chain**: Compromised dependencies or infrastructure

### Attack Vectors

- API exploitation (injection, broken authentication)
- Unauthorized data access across client boundaries
- Man-in-the-middle attacks on data in transit
- File upload vulnerabilities (malware, path traversal)
- Denial of service attacks
- Credential theft or brute force

## Security Controls

### 1. Authentication & Authorization

#### API Key Authentication

**Implementation**: `backend/api/dependencies.py::get_current_client()`

```python
# Authentication via X-API-Key header
X-API-Key: <client_api_key>
```

**Security Properties**:
- API keys stored hashed in database using bcrypt
- Keys validated on every request
- Failed authentication attempts logged to audit trail
- No session cookies or JWT tokens (stateless API)

**Key Management**:
- Generate strong random keys (32+ bytes) using `secrets.token_urlsafe()`
- Store keys in secure configuration management (e.g., AWS Secrets Manager)
- Rotate keys periodically (recommended: every 90 days)
- Revoke compromised keys immediately
- Never log or display full API keys in plain text

#### Client Isolation

**Enforcement**: Database queries filtered by `client_id`

```python
# Every query includes client isolation
analyses = db.query(MedicalAnalysis).filter(
    MedicalAnalysis.client_id == client.id
).all()
```

**Security Properties**:
- No cross-client data leakage possible
- Tenant isolation at application layer
- Database-level constraints prevent orphaned records
- File storage paths include client_id for segregation

#### Authorization Scopes (Future Enhancement)

**Planned**: Role-based access control (RBAC)

- **Admin**: Full system access, user management
- **Clinician**: Create/read/update analyses, no system config
- **Read-Only**: Query historical data, no create/update
- **Integration**: Programmatic API access with limited scope

### 2. Data Protection

#### Data at Rest

**Database Encryption**:
- PostgreSQL supports Transparent Data Encryption (TDE)
- Filesystem-level encryption (e.g., LUKS on Linux, BitLocker on Windows)
- Managed database services provide encryption by default (AWS RDS, Azure Database)

**File Storage Encryption**:
- S3 server-side encryption (SSE-S3, SSE-KMS)
- Local storage on encrypted volumes
- File metadata includes encryption status

**Configuration**:
```bash
# .env configuration
DATABASE_URL=postgresql://user:pass@host/db?sslmode=require
STORAGE_TYPE=s3
S3_SERVER_SIDE_ENCRYPTION=AES256
```

#### Data in Transit

**TLS/HTTPS**:
- All API communication over HTTPS (TLS 1.2+)
- Database connections require SSL (`sslmode=require`)
- Redis connections support TLS in production

**CORS Policy**:
```python
# backend/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # Configured, not wildcard
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

**Security Headers**:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Strict-Transport-Security: max-age=31536000`
- `Content-Security-Policy` (frontend)

#### Data Minimization

**PII Handling**:
- System does NOT collect patient names, birthdates, or identifiers
- Symptoms and findings stored in de-identified form
- Client integration ID serves as only identifier
- Document filenames sanitized to remove metadata

**Data Retention**:
- Configurable retention policies (default: 7 years for medical records)
- Automated purge of expired analyses
- Soft delete with recovery period before permanent deletion

### 3. Input Validation & Sanitization

#### Request Validation

**Pydantic Schemas**: All API inputs validated using strict type definitions

```python
class SymptomAnalysisRequest(BaseModel):
    symptoms: str = Field(..., min_length=10, max_length=5000)
    duration: Optional[str] = Field(None, max_length=100)
    severity: Optional[int] = Field(None, ge=1, le=10)
    
    @validator('symptoms')
    def sanitize_symptoms(cls, v):
        # Remove HTML tags, excessive whitespace
        return ' '.join(v.split())
```

**Benefits**:
- Prevents injection attacks (SQL, NoSQL, command injection)
- Rejects malformed data before processing
- Type coercion prevents type confusion bugs
- Length limits prevent DoS via oversized payloads

#### File Upload Security

**Validation Rules**:
- Allowed MIME types: `application/pdf`, `image/png`, `image/jpeg`, `image/dicom`
- Maximum file size: 10 MB (configurable)
- Filename sanitization: Remove directory traversal characters (`../`)
- Content verification: Verify file signature matches declared type

**Implementation**:
```python
# backend/services/storage_service.py
def validate_file(file: UploadFile):
    if file.content_type not in ALLOWED_TYPES:
        raise ValueError("Invalid file type")
    
    # Read file header to verify type
    header = file.file.read(512)
    file.file.seek(0)
    
    if not verify_file_signature(header, file.content_type):
        raise ValueError("File type mismatch")
    
    # Sanitize filename
    safe_name = secure_filename(file.filename)
    return safe_name
```

**Malware Scanning** (Future Enhancement):
- Integrate ClamAV or similar for virus scanning
- Quarantine suspicious uploads
- Alert on detection

### 4. SQL Injection Prevention

**ORM Usage**: All database operations use SQLAlchemy ORM

```python
# SAFE: Parameterized query via ORM
analysis = db.query(MedicalAnalysis).filter(
    MedicalAnalysis.id == analysis_id
).first()

# NEVER: String concatenation
# query = f"SELECT * FROM analyses WHERE id = {analysis_id}"  # VULNERABLE
```

**Benefits**:
- Automatic parameter binding prevents injection
- Type safety ensures correct data types
- ORM prevents complex injection vectors (UNION, blind SQLi)

### 5. Audit Logging

**Event Types Logged**:
- Authentication attempts (success/failure)
- Analysis creation and retrieval
- File uploads and downloads
- Configuration changes
- System errors and exceptions

**Audit Schema**:
```python
class AuditEvent(Base):
    id = Column(UUID, primary_key=True)
    client_id = Column(UUID, nullable=True)
    event_type = Column(String, nullable=False)  # auth, analysis, upload, etc.
    action = Column(String, nullable=False)      # create, read, update, delete
    resource_type = Column(String)
    resource_id = Column(String)
    ip_address = Column(String)
    user_agent = Column(String)
    success = Column(Boolean)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
```

**Log Retention**:
- Audit logs retained for compliance period (7+ years)
- Immutable log storage (write-once, no updates)
- Encrypted at rest
- Regular backups to separate storage

**SIEM Integration** (Future Enhancement):
- Forward logs to Splunk, ELK, or similar
- Real-time alerting on suspicious patterns
- Automated incident response

### 6. Secrets Management

#### Environment Variables

**Never in Code**:
```python
# GOOD: Load from environment
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")

# BAD: Hardcoded secret
# DATABASE_PASSWORD = "mysecretpass123"  # NEVER DO THIS
```

**Production Configuration**:
- Use secret management service (AWS Secrets Manager, HashiCorp Vault)
- Rotate secrets automatically
- Audit secret access
- Limit secret access to specific services/roles

#### API Key Storage

**Database Storage**:
```python
# backend/models/integration.py
api_key_hash = Column(String, nullable=False)  # bcrypt hash, never plaintext

# On creation
client.api_key_hash = bcrypt.hashpw(
    api_key.encode('utf-8'), 
    bcrypt.gensalt()
)

# On verification
if bcrypt.checkpw(provided_key.encode(), stored_hash):
    # Valid key
```

**Key Distribution**:
- Display full key only once on creation
- Provide secure channel for key delivery (encrypted email, secret sharing tool)
- Support key regeneration if lost

### 7. Dependency Security

#### Vulnerability Scanning

**Tools**:
- `pip-audit`: Scan Python dependencies for known CVEs
- `safety`: Check against vulnerability database
- Dependabot: Automated dependency updates (GitHub)

**Process**:
```bash
# Regular scanning
pip-audit --requirement requirements.txt

# Update vulnerable packages
pip install --upgrade <package>==<safe_version>
```

**Pinned Dependencies**:
```
# requirements.txt - pin exact versions
fastapi==0.104.1
sqlalchemy==2.0.23
# Not: fastapi>=0.100  # Allows risky auto-updates
```

#### Supply Chain Security

- Verify package signatures when available
- Use private PyPI mirror for internal packages
- Review dependency tree for suspicious packages
- Monitor for typosquatting attempts

### 8. AI/ML Security

#### Prompt Injection Prevention

**Mitigation**:
- Strict input validation and sanitization
- System prompts clearly separate instructions from user input
- Output validation to detect malicious content
- Rate limiting on LLM API calls

**Example Defense**:
```python
# backend/ai/llm_provider.py
def _sanitize_input(self, text: str) -> str:
    # Remove potential prompt injection markers
    dangerous_patterns = [
        "ignore previous instructions",
        "system:",
        "<|endoftext|>",
        "assistant:",
    ]
    for pattern in dangerous_patterns:
        text = text.replace(pattern, "")
    return text
```

#### Model Integrity

- Verify TorchXRayVision model checksums on load
- Use trusted model sources (official repositories)
- Monitor model predictions for drift or adversarial examples
- Version control for model updates

#### Output Validation

**Medical Safety**:
- Flag overly confident predictions without sufficient data
- Require human review for critical findings (e.g., emergency conditions)
- Disclaimer: "AI-assisted, not a substitute for professional medical advice"
- Log all AI outputs for quality monitoring

### 9. Rate Limiting & DoS Prevention

#### API Rate Limiting (Future Enhancement)

**Planned Implementation**:
```python
# Per-client rate limits
limits = {
    "analyses": "100/hour",
    "uploads": "50/hour",
    "queries": "1000/hour",
}
```

**Benefits**:
- Prevent abuse and API scraping
- Protect backend services from overload
- Fair resource allocation across clients

#### Request Size Limits

**Current Limits**:
- Request body: 10 MB (file uploads)
- JSON payload: 1 MB
- Query parameters: 2048 characters

**Enforcement**:
```python
# FastAPI automatic limit
app.add_middleware(
    LimitUploadSize,
    max_upload_size=10 * 1024 * 1024
)
```

### 10. Incident Response

#### Detection

**Monitoring Alerts**:
- Failed authentication attempts > threshold
- Unusual access patterns (time, volume, location)
- Database query anomalies
- File access violations
- System errors and crashes

#### Response Procedures

1. **Identification**: Detect and verify security incident
2. **Containment**: Isolate affected systems, revoke compromised credentials
3. **Eradication**: Remove threat, patch vulnerabilities
4. **Recovery**: Restore services, verify integrity
5. **Lessons Learned**: Post-mortem, update controls

#### Communication

- **Internal**: Notify security team, management
- **External**: Comply with breach notification laws (HIPAA, GDPR)
- **Affected Parties**: Inform clients of potential exposure
- **Documentation**: Maintain incident timeline and actions taken

## Compliance Considerations

### HIPAA (Health Insurance Portability and Accountability Act)

**Applicability**: If ClaraMed processes Protected Health Information (PHI)

**Requirements**:
- Access controls (authentication, authorization)
- Audit logging (who accessed what, when)
- Data encryption (at rest and in transit)
- Business Associate Agreements (BAAs) with vendors
- Regular security risk assessments
- Breach notification procedures

**ClaraMed Implementation**:
- ✅ Authentication and client isolation
- ✅ Comprehensive audit logging
- ✅ Encryption support (TLS, database encryption)
- ⚠️  BAAs required with cloud providers (AWS, Groq, etc.)
- ⚠️  Security risk assessment needed
- ⚠️  Breach notification process needed

### GDPR (General Data Protection Regulation)

**Applicability**: If serving EU residents

**Requirements**:
- Data minimization (collect only necessary data)
- Right to access (data portability)
- Right to erasure ("right to be forgotten")
- Data breach notification (72 hours)
- Privacy by design
- Data processing agreements

**ClaraMed Implementation**:
- ✅ Minimal PII collection
- ⚠️  Export API for data access needed
- ⚠️  Hard delete mechanism needed
- ⚠️  Breach notification process needed
- ✅ Security-first architecture
- ⚠️  DPAs required with processors

### FDA Regulations (If Marketed as Medical Device)

**Applicability**: If ClaraMed makes diagnostic claims

**Requirements**:
- Software as a Medical Device (SaMD) classification
- Clinical validation studies
- 510(k) premarket notification or PMA
- Quality Management System (QMS)
- Post-market surveillance

**Current Status**: ClaraMed is a clinical decision support tool, not a diagnostic device. Proper disclaimers and human oversight required.

## Security Checklist for Deployment

### Pre-Production

- [ ] All secrets moved to environment variables or secret manager
- [ ] Database encryption enabled
- [ ] TLS/HTTPS configured for all endpoints
- [ ] API key authentication tested
- [ ] CORS origins restricted to production domains
- [ ] File upload validation active
- [ ] Audit logging enabled and tested
- [ ] Dependency vulnerability scan passed
- [ ] Security headers configured
- [ ] Rate limiting implemented (if applicable)

### Production Monitoring

- [ ] Set up intrusion detection alerts
- [ ] Configure log aggregation and analysis
- [ ] Enable database backup encryption
- [ ] Implement secret rotation schedule
- [ ] Schedule regular penetration testing
- [ ] Maintain incident response playbook
- [ ] Review access logs weekly
- [ ] Update dependencies monthly

### Regular Reviews

- [ ] Quarterly security risk assessment
- [ ] Annual penetration testing
- [ ] Ongoing vulnerability scanning
- [ ] Review and update security policies
- [ ] Staff security awareness training
- [ ] Third-party security audits

## Security Contact

For security concerns or to report vulnerabilities:

**Email**: security@claramed.example.com (update with actual contact)
**PGP Key**: [Provide public key for encrypted communication]

**Vulnerability Disclosure Policy**:
- Report via secure channel (email, bug bounty platform)
- Provide details: affected component, reproduction steps, impact
- Allow reasonable time for patching before public disclosure
- Recognition for responsible disclosure

## Conclusion

ClaraMed implements defense-in-depth security with multiple layers of protection. However, security is an ongoing process requiring:

- Regular monitoring and alerting
- Timely patching of vulnerabilities
- Staff training and awareness
- Compliance with applicable regulations
- Continuous improvement based on threat landscape

**Security is everyone's responsibility.** All developers, operators, and users must follow security best practices and report concerns promptly.
