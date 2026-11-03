#!/usr/bin/env python3
"""
Check that all required dependencies are installed and available.

Run this script before starting ClaraMed to verify environment setup.
"""
import sys
import subprocess
from pathlib import Path


def check_python_version():
    """Verify Python version is 3.11+."""
    print("Checking Python version...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        print(f"  ❌ Python 3.11+ required, found {version.major}.{version.minor}")
        return False
    print(f"  ✓ Python {version.major}.{version.minor}.{version.micro}")
    return True


def check_package(package_name, import_name=None):
    """Check if a Python package is installed."""
    if import_name is None:
        import_name = package_name
    
    try:
        __import__(import_name)
        print(f"  ✓ {package_name}")
        return True
    except ImportError:
        print(f"  ❌ {package_name} not installed")
        return False


def check_python_packages():
    """Check all required Python packages."""
    print("\nChecking Python packages...")
    
    packages = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("sqlalchemy", "sqlalchemy"),
        ("alembic", "alembic"),
        ("pydantic", "pydantic"),
        ("psycopg2-binary", "psycopg2"),
        ("celery", "celery"),
        ("redis", "redis"),
        ("torchxrayvision", "torchxrayvision"),
        ("torch", "torch"),
        ("pillow", "PIL"),
        ("pytesseract", "pytesseract"),
        ("PyPDF2", "PyPDF2"),
        ("langchain", "langchain"),
        ("langchain-groq", "langchain_groq"),
        ("streamlit", "streamlit"),
        ("python-multipart", "multipart"),
        ("python-dotenv", "dotenv"),
        ("bcrypt", "bcrypt"),
    ]
    
    all_ok = True
    for package_name, import_name in packages:
        if not check_package(package_name, import_name):
            all_ok = False
    
    return all_ok


def check_tesseract():
    """Check if Tesseract OCR is installed and accessible."""
    print("\nChecking Tesseract OCR...")
    try:
        result = subprocess.run(
            ["tesseract", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"  ✓ {version_line}")
            return True
        else:
            print("  ❌ Tesseract command failed")
            return False
    except FileNotFoundError:
        print("  ❌ Tesseract not found in PATH")
        print("     Install from: https://github.com/tesseract-ocr/tesseract")
        print("     Windows: Download installer from GitHub releases")
        print("     Linux: sudo apt-get install tesseract-ocr")
        print("     macOS: brew install tesseract")
        return False
    except Exception as e:
        print(f"  ❌ Error checking Tesseract: {e}")
        return False


def check_environment_file():
    """Check if .env file exists and has required variables."""
    print("\nChecking environment configuration...")
    
    env_path = Path(".env")
    if not env_path.exists():
        print("  ⚠️  .env file not found")
        print("     Copy .env.example to .env and configure")
        return False
    
    print("  ✓ .env file exists")
    
    # Check for critical variables
    required_vars = [
        "DATABASE_URL",
        "GROQ_API_KEY",
        "REDIS_URL",
        "SECRET_KEY"
    ]
    
    with open(env_path) as f:
        env_content = f.read()
    
    missing_vars = []
    for var in required_vars:
        if f"{var}=" not in env_content or f"{var}=" in env_content and "your_" in env_content:
            missing_vars.append(var)
    
    if missing_vars:
        print(f"  ⚠️  Missing or unconfigured variables: {', '.join(missing_vars)}")
        return False
    
    print("  ✓ Required environment variables present")
    return True


def check_database_connection():
    """Check if can connect to PostgreSQL database."""
    print("\nChecking database connection...")
    
    try:
        from dotenv import load_dotenv
        import os
        from sqlalchemy import create_engine
        
        load_dotenv()
        database_url = os.getenv("DATABASE_URL")
        
        if not database_url:
            print("  ⚠️  DATABASE_URL not set")
            return False
        
        # Try to connect
        engine = create_engine(database_url)
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
            result.fetchone()
        
        print("  ✓ Database connection successful")
        return True
    
    except Exception as e:
        print(f"  ❌ Database connection failed: {e}")
        print("     Ensure PostgreSQL is running and DATABASE_URL is correct")
        return False


def check_redis_connection():
    """Check if can connect to Redis."""
    print("\nChecking Redis connection...")
    
    try:
        from dotenv import load_dotenv
        import os
        import redis
        
        load_dotenv()
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        
        # Try to connect
        r = redis.from_url(redis_url)
        r.ping()
        
        print("  ✓ Redis connection successful")
        return True
    
    except Exception as e:
        print(f"  ❌ Redis connection failed: {e}")
        print("     Ensure Redis is running and REDIS_URL is correct")
        return False


def check_storage_directory():
    """Check if storage directory exists and is writable."""
    print("\nChecking storage configuration...")
    
    try:
        from dotenv import load_dotenv
        import os
        
        load_dotenv()
        storage_type = os.getenv("STORAGE_TYPE", "local")
        
        if storage_type == "local":
            storage_path = Path(os.getenv("LOCAL_STORAGE_PATH", "./storage"))
            
            if not storage_path.exists():
                print(f"  ⚠️  Storage directory {storage_path} does not exist")
                print(f"     Creating...")
                storage_path.mkdir(parents=True, exist_ok=True)
            
            # Check if writable
            test_file = storage_path / ".write_test"
            try:
                test_file.write_text("test")
                test_file.unlink()
                print(f"  ✓ Storage directory writable: {storage_path.absolute()}")
                return True
            except Exception as e:
                print(f"  ❌ Storage directory not writable: {e}")
                return False
        
        elif storage_type == "s3":
            print(f"  ✓ Using S3 storage (ensure AWS credentials configured)")
            return True
        
        else:
            print(f"  ⚠️  Unknown storage type: {storage_type}")
            return False
    
    except Exception as e:
        print(f"  ❌ Error checking storage: {e}")
        return False


def check_model_availability():
    """Check if AI models can be loaded."""
    print("\nChecking AI model availability...")
    
    # Check TorchXRayVision model
    print("  Checking TorchXRayVision model...")
    try:
        import torchxrayvision as xrv
        model = xrv.models.DenseNet(weights="densenet121-res224-all")
        print("    ✓ TorchXRayVision model loaded")
    except Exception as e:
        print(f"    ⚠️  TorchXRayVision model load issue: {e}")
        print("       Model will download on first use")
    
    # Check Groq API key
    print("  Checking LLM API access...")
    try:
        from dotenv import load_dotenv
        import os
        
        load_dotenv()
        api_key = os.getenv("GROQ_API_KEY")
        
        if not api_key or api_key.startswith("your_"):
            print("    ❌ GROQ_API_KEY not configured")
            return False
        
        # Try a simple API call
        from langchain_groq import ChatGroq
        llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.7)
        response = llm.invoke("Say 'API working'")
        
        if response and "working" in response.content.lower():
            print("    ✓ Groq API accessible")
            return True
        else:
            print("    ⚠️  Unexpected API response")
            return False
    
    except Exception as e:
        print(f"    ❌ LLM API check failed: {e}")
        return False


def main():
    """Run all dependency checks."""
    print("=" * 60)
    print("ClaraMed Dependency Check")
    print("=" * 60)
    
    checks = [
        check_python_version(),
        check_python_packages(),
        check_tesseract(),
        check_environment_file(),
    ]
    
    # Optional checks (won't fail overall if these fail)
    optional_checks = [
        check_database_connection(),
        check_redis_connection(),
        check_storage_directory(),
        check_model_availability(),
    ]
    
    print("\n" + "=" * 60)
    
    if all(checks):
        print("✓ All required dependencies satisfied")
        
        if all(optional_checks):
            print("✓ All services accessible and ready")
            print("\nYou can start ClaraMed with:")
            print("  docker-compose up")
            print("  or")
            print("  uvicorn backend.main:app --reload")
            sys.exit(0)
        else:
            print("⚠️  Some services need configuration")
            print("\nReview warnings above and start required services:")
            print("  - PostgreSQL database")
            print("  - Redis server")
            print("  - Configure .env file")
            sys.exit(1)
    else:
        print("❌ Missing required dependencies")
        print("\nInstall missing packages:")
        print("  pip install -r requirements.txt")
        sys.exit(1)


if __name__ == "__main__":
    main()
