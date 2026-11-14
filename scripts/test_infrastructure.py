"""
Comprehensive Infrastructure Test Script
Tests all ClaraMed components independently
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_python_environment():
    """Test Python version and virtual environment"""
    print("\n=== Python Environment ===")
    print(f"Python version: {sys.version}")
    print(f"Python executable: {sys.executable}")
    print(f"Virtual environment: {hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)}")
    return True

def test_core_imports():
    """Test core Python package imports"""
    print("\n=== Core Package Imports ===")
    packages = [
        "psycopg2",
        "sqlalchemy",
        "alembic",
        "redis",
        "celery",
        "groq",
        "langchain_groq",
        "pytesseract",
        "torch",
        "torchxrayvision",
        "fastapi",
        "streamlit",
    ]
    
    for package in packages:
        try:
            __import__(package)
            print(f"[OK] {package}")
        except ImportError as e:
            print(f"[FAIL] {package}: {e}")
            return False
    return True

def test_groq_api():
    """Test Groq API connectivity"""
    print("\n=== Groq API Test ===")
    try:
        from groq import Groq
        import os
        
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        
        # Test with minimal request
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": "test"}],
            model="openai/gpt-oss-120b",
            max_tokens=5,
        )
        
        result = response.choices[0].message.content
        print(f"[OK] Groq API working")
        print(f"  Model: openai/gpt-oss-120b")
        print(f"  Response: {result}")
        return True
    except Exception as e:
        print(f"[FAIL] Groq API failed: {e}")
        return False

def test_tesseract_ocr():
    """Test Tesseract OCR"""
    print("\n=== Tesseract OCR Test ===")
    try:
        import pytesseract
        from PIL import Image, ImageDraw
        
        # Configure Tesseract
        pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD", r"C:/Program Files/Tesseract-OCR/tesseract.exe")
        
        # Check version
        version = pytesseract.get_tesseract_version()
        print(f"[OK] Tesseract version: {version}")
        
        # Create test image
        img = Image.new('RGB', (400, 100), color='white')
        d = ImageDraw.Draw(img)
        d.text((10, 30), "Medical Report Test", fill='black')
        
        # Perform OCR
        text = pytesseract.image_to_string(img)
        print(f"  OCR result: {text.strip()}")
        
        return "Medical" in text or "Report" in text
    except Exception as e:
        print(f"[FAIL] Tesseract OCR failed: {e}")
        return False

def test_redis():
    """Test Redis connectivity"""
    print("\n=== Redis Test ===")
    try:
        import redis
        
        # redis-py 8.x with RESP2 for Redis 3.x compatibility
        r = redis.StrictRedis(
            host='localhost',
            port=6379,
            db=0,
            decode_responses=True,
            protocol=2  # Force RESP2 for Redis 3.x
        )
        
        # Test PING
        result = r.ping()
        print(f"[OK] Redis PING: {result}")
        
        # Test SET/GET
        r.set('claramed_test', 'hello')
        value = r.get('claramed_test')
        print(f"  SET/GET test: {value}")
        r.delete('claramed_test')
        
        # Get info
        info = r.info()
        print(f"  Version: {info['redis_version']}")
        
        return True
    except Exception as e:
        print(f"[FAIL] Redis failed: {e}")
        return False

def test_celery_config():
    """Test Celery configuration"""
    print("\n=== Celery Configuration Test ===")
    try:
        from backend.workers.celery_app import celery_app
        
        print(f"[OK] Celery app created")
        print(f"  Broker: {celery_app.conf.broker_url}")
        print(f"  Backend: {celery_app.conf.result_backend}")
        print(f"  Serializer: {celery_app.conf.task_serializer}")
        
        # Inspect broker connection
        try:
            inspect = celery_app.control.inspect()
            print(f"  Control created successfully")
        except Exception as e:
            print(f"  Note: Worker not running (expected): {e}")
        
        return True
    except Exception as e:
        print(f"[FAIL] Celery config failed: {e}")
        return False

def test_pytorch_radiology():
    """Test PyTorch and radiology model"""
    print("\n=== PyTorch & Radiology AI Test ===")
    try:
        import torch
        import torchxrayvision as xrv
        import numpy as np
        
        print(f"[OK] PyTorch version: {torch.__version__}")
        print(f"  TorchXRayVision version: {xrv.__version__}")
        print(f"  Device: CPU (cuda available: {torch.cuda.is_available()})")
        
        # Set cache directory
        os.environ['TORCH_HOME'] = 'D:/ClaraMedCache/models'
        
        # Load model
        print("  Loading densenet121-res224-all...")
        model = xrv.models.DenseNet(weights='densenet121-res224-all')
        model.eval()
        
        print(f"[OK] Model loaded")
        print(f"  Pathologies: {model.pathologies[:5]}...")
        
        # Test inference with synthetic data
        print("  Testing inference with synthetic data...")
        with torch.no_grad():
            # Create synthetic chest X-ray (224x224)
            img = np.random.rand(1, 224, 224).astype(np.float32)
            img_tensor = torch.from_numpy(img)
            
            # Run inference
            outputs = model(img_tensor)
            print(f"[OK] Inference successful")
            print(f"  Output shape: {outputs.shape}")
        
        return True
    except Exception as e:
        print(f"[FAIL] PyTorch/Radiology test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_postgresql():
    """Test PostgreSQL connectivity"""
    print("\n=== PostgreSQL Test ===")
    try:
        import psycopg2
        
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        print(f"[OK] PostgreSQL connected")
        
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"  Version: {version[0].split(',')[0]}")
        
        cursor.execute("SELECT current_user, current_database();")
        user, db = cursor.fetchone()
        print(f"  User: {user}, Database: {db}")
        
        conn.close()
        return True
    except Exception as e:
        print(f"[FAIL] PostgreSQL connection failed: {e}")
        print(f"\n  -> Password reset required. Run: .\\scripts\\reset_postgres_password.ps1")
        return False

def test_backend_imports():
    """Test backend module imports"""
    print("\n=== Backend Module Imports ===")
    try:
        from backend.core.config import settings
        print(f"[OK] Backend config loaded")
        print(f"  App: {settings.APP_NAME} v{settings.APP_VERSION}")
        print(f"  Environment: {settings.APP_ENV}")
        
        from backend.models import (
            MedicalAnalysis,
            AnalysisResult,
            UploadedDocument,
            RadiologyFinding,
            IntegrationClient,
            AuditEvent,
        )
        print(f"[OK] All models imported")
        
        from backend.database.connection import Base
        print(f"[OK] Database Base imported")
        print(f"  Tables: {list(Base.metadata.tables.keys())}")
        
        return True
    except Exception as e:
        print(f"[FAIL] Backend imports failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("ClaraMed Infrastructure Test Suite")
    print("=" * 60)
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    results = {
        "Python Environment": test_python_environment(),
        "Core Imports": test_core_imports(),
        "Backend Imports": test_backend_imports(),
        "Groq API": test_groq_api(),
        "Tesseract OCR": test_tesseract_ocr(),
        "Redis": test_redis(),
        "Celery Config": test_celery_config(),
        "PyTorch & Radiology": test_pytorch_radiology(),
        "PostgreSQL": test_postgresql(),
    }
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status:8} {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if not results["PostgreSQL"]:
        print("\n[!] Action Required:")
        print("  Run: .\\scripts\\reset_postgres_password.ps1")
        print("  This will reset the PostgreSQL 'claramed' user password.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
