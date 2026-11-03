# ClaraMed 🩺 — AI-Powered Medical Analysis Platform

ClaraMed is an independent AI-powered medical information and analysis platform providing symptom analysis, medical document processing with OCR, and chest X-ray analysis using deep learning.

---

## 🌟 Key Features

### 1. **AI-Powered Symptom Analysis**
- Educational symptom explanations using LLM (Groq/Llama-3.1)
- Conservative emergency classification
- Personalized wellness and lifestyle suggestions
- Multilingual support (7 languages)

### 2. **Medical Document Intelligence**
- PDF text extraction (PyPDF2)
- **Tesseract OCR** for scanned documents
- Structured finding extraction
- Plain-language report explanations

### 3. **Radiology AI (TorchXRayVision)**
- **Chest X-ray analysis** using pretrained deep learning models
- Automated pathology detection (14 findings)
- Model: densenet121-res224-all
- Real inference with actual model loading

### 4. **Production-Ready Architecture**
- FastAPI backend with REST API
- PostgreSQL database with persistent storage
- Celery + Redis background processing
- S3-compatible file storage
- Docker deployment ready

### 5. **Comprehensive Security**
- API key authentication
- Cross-client data isolation
- Secure file handling
- Audit logging

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| Backend API | FastAPI |
| Frontend UI | Streamlit |
| Database | PostgreSQL |
| Background Jobs | Celery + Redis |
| AI/LLM | Groq API (Llama-3.1) |
| Radiology AI | TorchXRayVision (PyTorch) |
| OCR | Tesseract OCR |
| PDF Processing | PyPDF2 |
| File Storage | Local / S3-compatible |
| Deployment | Docker + Docker Compose |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose (recommended)
- Tesseract OCR
- Groq API Key

### Option 1: Docker Compose (Recommended)

1. **Clone the repository:**
```bash
git clone https://github.com/KunalMK25/claramed.git
cd claramed
```

2. **Set up environment:**
```bash
cp .env.example .env
# Edit .env and set GROQ_API_KEY
```

3. **Start all services:**
```bash
docker-compose up -d
```

4. **Access the application:**
- Frontend: http://localhost:8501
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/api/docs

### Option 2: Local Development

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Install Tesseract OCR:**
- **Windows:** Download from https://github.com/UB-Mannheim/tesseract/wiki
- **Linux:** `sudo apt-get install tesseract-ocr`
- **macOS:** `brew install tesseract`

3. **Set up PostgreSQL:**
```bash
# Create database
createdb claramed
```

4. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your settings
```

5. **Run migrations:**
```bash
alembic upgrade head
```

6. **Start services:**

Terminal 1 - Backend:
```bash
python backend/main.py
```

Terminal 2 - Worker:
```bash
celery -A backend.workers.celery_app worker --loglevel=info
```

Terminal 3 - Frontend:
```bash
streamlit run app_new.py
```

---

## 📚 API Usage

### Symptom Analysis

```bash
curl -X POST http://localhost:8000/api/v1/analyses \
  -H "Content-Type: application/json" \
  -d '{
    "symptoms": "I have a headache and feel nauseous",
    "language": "English",
    "include_wellness": true
  }'
```

### Document Upload

```bash
curl -X POST http://localhost:8000/api/v1/analyses/{analysis_id}/documents \
  -F "file=@medical_report.pdf"
```

### Radiology Analysis

```bash
curl -X POST http://localhost:8000/api/v1/analyses/{analysis_id}/images \
  -F "file=@chest_xray.png"
```

See [docs/API.md](docs/API.md) for complete API documentation.

---

## 🧪 Testing

Run tests:
```bash
pytest tests/ -v
```

Run specific test suite:
```bash
pytest tests/unit/ -v
pytest tests/api/ -v
```

---

## 📖 Documentation

- [API Documentation](docs/API.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Architecture Overview](docs/ARCHITECTURE.md)
- [Security Guidelines](docs/SECURITY.md)
- [Model Limitations](docs/MODEL_LIMITATIONS.md)

---

## 🔐 Security & Medical Safety

### Important Disclaimers

⚠️ **ClaraMed is for educational and informational purposes only.**

- **Not a diagnostic tool** - AI outputs require professional medical interpretation
- **Not FDA-approved** - Not validated for clinical decision-making
- **Not a replacement for medical care** - Always consult healthcare professionals
- **Emergency situations** - Call emergency services immediately if you believe you have a medical emergency

### Data Handling

- Patient data isolation enforced
- Secure file storage
- No PHI in logs
- Audit trails maintained
- HIPAA-conscious design (not certified)

---

## 🌍 Multilingual Support

- English
- Hindi (हिन्दी)
- Kannada (ಕನ್ನಡ)
- Tamil (தமிழ்)
- Telugu (తెలుగు)
- Spanish (Español)
- French (Français)

---

## 🔄 JeevaCare Integration

ClaraMed is designed for future integration with JeevaCare healthcare platform while operating independently.

**Integration Interface:**
- REST API with versioned endpoints
- External patient/hospital references
- Service-to-service authentication
- Webhook notifications (optional)

See [BUILD.md](BUILD.md) for integration specifications.

---

## 📦 Project Structure

```
claramed/
├── backend/
│   ├── api/           # FastAPI routes
│   ├── core/          # Configuration, security
│   ├── models/        # Database models
│   ├── services/      # Business logic
│   ├── ai/            # LLM integration
│   └── workers/       # Celery tasks
├── frontend/          # Streamlit UI
├── tests/             # Test suite
├── docs/              # Documentation
├── migrations/        # Alembic migrations
└── docker-compose.yml # Deployment config
```

---

## 🤝 Contributing

Contributions welcome! Please ensure:

1. Tests pass: `pytest tests/`
2. Code follows project style
3. Documentation updated
4. Medical disclaimers preserved

---

## 📝 License

[Add appropriate license]

---

## ⚠️ Disclaimer

**ClaraMed is for educational purposes only. It is not a medical device, not FDA-approved, and not a substitute for professional medical advice, diagnosis, or treatment. Always seek the advice of your physician or other qualified health provider with any questions about a medical condition.**

**In case of emergency, call your local emergency services immediately.**

---

## 🙏 Acknowledgments

- TorchXRayVision for chest X-ray models
- Groq for LLM API
- Tesseract OCR project
- Open-source medical AI community
