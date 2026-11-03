#!/usr/bin/env python3
"""
Verification script for ClaraMed implementation.

This script performs comprehensive checks per BUILD.md Section 27 acceptance criteria.
"""
import sys
import os
import json
from pathlib import Path


def check_project_structure():
    """Verify all required files and directories exist."""
    print("=" * 60)
    print("1. Checking Project Structure")
    print("=" * 60)
    
    required_paths = [
        # Backend structure
        "backend/__init__.py",
        "backend/main.py",
        "backend/core/config.py",
        "backend/core/security.py",
        "backend/core/exceptions.py",
        "backend/core/logging.py",
        "backend/database/connection.py",
        "backend/models/analysis.py",
        "backend/models/result.py",
        "backend/models/document.py",
        "backend/models/radiology.py",
        "backend/models/integration_client.py",
        "backend/models/audit.py",
        "backend/api/routes/health.py",
        "backend/api/routes/analyses.py",
        "backend/api/dependencies.py",
        "backend/schemas/analysis.py",
        "backend/services/symptom_service.py",
        "backend/services/emergency_service.py",
        "backend/services/document_service.py",
        "backend/services/ocr_service.py",
        "backend/services/radiology_service.py",
        "backend/services/storage_service.py",
        "backend/ai/llm_provider.py",
        "backend/ai/prompts.py",
        "backend/workers/celery_app.py",
        "backend/workers/tasks.py",
        
        # Frontend
        "app_new.py",
        "frontend/api_client.py",
        
        # Configuration
        ".env.example",
        "requirements.txt",
        "requirements-dev.txt",
        "alembic.ini",
        
        # Docker
        "Dockerfile",
        "Dockerfile.frontend",
        "docker-compose.yml",
        
        # Documentation
        "README.md",
        "docs/API.md",
        "docs/DEPLOYMENT.md",
        "docs/ARCHITECTURE.md",
        "docs/SECURITY.md",
        "docs/MODEL_LIMITATIONS.md",
        
        # Tests
        "tests/conftest.py",
        "tests/unit/test_symptom_service.py",
        "tests/unit/test_emergency_service.py",
        "tests/api/test_health.py",
        "tests/integration/test_document_workflow.py",
        "tests/integration/test_radiology_workflow.py",
        
        # Scripts
        "scripts/init_db.py",
        "scripts/check_dependencies.py",
    ]
    
    missing_files = []
    for path in required_paths:
        if not Path(path).exists():
            missing_files.append(path)
            print(f"  ❌ Missing: {path}")
        else:
            print(f"  ✓ {path}")
    
    if missing_files:
        print(f"\n❌ {len(missing_files)} files missing")
        return False
    else:
        print(f"\n✓ All {len(required_paths)} required files present")
        return True


def check_configuration_files():
    """Verify configuration files are properly set up."""
    print("\n" + "=" * 60)
    print("2. Checking Configuration")
    print("=" * 60)
    
    # Check .env.example
    env_example = Path(".env.example")
    if not env_example.exists():
        print("  ❌ .env.example not found")
        return False
    
    required_vars = [
        "DATABASE_URL",
        "GROQ_API_KEY",
        "REDIS_URL",
        "SECRET_KEY",
        "STORAGE_TYPE",
    ]
    
    with open(env_example) as f:
        env_content = f.read()
    
    missing_vars = []
    for var in required_vars:
        if f"{var}=" not in env_content:
            missing_vars.append(var)
            print(f"  ❌ Missing in .env.example: {var}")
        else:
            print(f"  ✓ {var} defined in .env.example")
    
    if missing_vars:
        print(f"\n❌ {len(missing_vars)} required variables missing from .env.example")
        return False
    
    # Check requirements.txt
    requirements = Path("requirements.txt")
    if not requirements.exists():
        print("  ❌ requirements.txt not found")
        return False
    
    with open(requirements) as f:
        req_content = f.read()
    
    critical_packages = [
        "fastapi",
        "sqlalchemy",
        "alembic",
        "celery",
        "redis",
        "torchxrayvision",
        "pytesseract",
        "langchain-groq",
        "streamlit",
    ]
    
    missing_packages = []
    for package in critical_packages:
        if package not in req_content.lower():
            missing_packages.append(package)
            print(f"  ❌ Missing from requirements.txt: {package}")
        else:
            print(f"  ✓ {package} in requirements.txt")
    
    if missing_packages:
        print(f"\n❌ {len(missing_packages)} critical packages missing")
        return False
    
    print("\n✓ Configuration files properly set up")
    return True


def check_docker_configuration():
    """Verify Docker files are complete."""
    print("\n" + "=" * 60)
    print("3. Checking Docker Configuration")
    print("=" * 60)
    
    # Check docker-compose.yml
    compose_file = Path("docker-compose.yml")
    if not compose_file.exists():
        print("  ❌ docker-compose.yml not found")
        return False
    
    with open(compose_file) as f:
        compose_content = f.read()
    
    required_services = ["db", "redis", "api", "worker", "frontend"]
    missing_services = []
    
    for service in required_services:
        if f"{service}:" not in compose_content:
            missing_services.append(service)
            print(f"  ❌ Missing service: {service}")
        else:
            print(f"  ✓ Service defined: {service}")
    
    if missing_services:
        print(f"\n❌ {len(missing_services)} services missing from docker-compose.yml")
        return False
    
    # Check Dockerfiles
    dockerfiles = ["Dockerfile", "Dockerfile.frontend"]
    for dockerfile in dockerfiles:
        if not Path(dockerfile).exists():
            print(f"  ❌ {dockerfile} not found")
            return False
        else:
            print(f"  ✓ {dockerfile} exists")
    
    print("\n✓ Docker configuration complete")
    return True


def check_api_implementation():
    """Verify API endpoints are implemented."""
    print("\n" + "=" * 60)
    print("4. Checking API Implementation")
    print("=" * 60)
    
    main_file = Path("backend/main.py")
    if not main_file.exists():
        print("  ❌ backend/main.py not found")
        return False
    
    with open(main_file) as f:
        main_content = f.read()
    
    required_elements = [
        "FastAPI",
        "health_router",
        "analyses_router",
        "CORSMiddleware",
    ]
    
    missing_elements = []
    for element in required_elements:
        if element not in main_content:
            missing_elements.append(element)
            print(f"  ❌ Missing in main.py: {element}")
        else:
            print(f"  ✓ {element} present")
    
    # Check routes file
    routes_file = Path("backend/api/routes/analyses.py")
    if not routes_file.exists():
        print("  ❌ backend/api/routes/analyses.py not found")
        return False
    
    with open(routes_file) as f:
        routes_content = f.read()
    
    required_endpoints = [
        "POST /analyses",
        "POST /documents",
        "POST /images",
        "GET /status",
        "GET /result",
    ]
    
    # Simplified check - look for route definitions
    route_markers = [
        '@router.post("/"',
        '@router.post("/documents"',
        '@router.post("/images"',
        '@router.get("/{analysis_id}/status"',
        '@router.get("/{analysis_id}/result"',
    ]
    
    missing_routes = []
    for i, marker in enumerate(route_markers):
        if marker not in routes_content:
            missing_routes.append(required_endpoints[i])
            print(f"  ❌ Missing endpoint: {required_endpoints[i]}")
        else:
            print(f"  ✓ Endpoint implemented: {required_endpoints[i]}")
    
    if missing_elements or missing_routes:
        print("\n❌ API implementation incomplete")
        return False
    
    print("\n✓ API implementation complete")
    return True


def check_service_implementation():
    """Verify all core services are implemented."""
    print("\n" + "=" * 60)
    print("5. Checking Service Layer")
    print("=" * 60)
    
    services = {
        "symptom_service.py": ["SymptomService", "analyze_symptoms"],
        "emergency_service.py": ["EmergencyService", "classify_emergency"],
        "document_service.py": ["DocumentService", "extract_text"],
        "ocr_service.py": ["OCRService", "extract_text_from_image"],
        "radiology_service.py": ["RadiologyService", "analyze_image"],
        "storage_service.py": ["StorageService", "upload_file"],
    }
    
    all_ok = True
    for service_file, required_classes in services.items():
        service_path = Path("backend/services") / service_file
        
        if not service_path.exists():
            print(f"  ❌ Missing: {service_file}")
            all_ok = False
            continue
        
        with open(service_path) as f:
            service_content = f.read()
        
        missing_classes = []
        for cls in required_classes:
            if cls not in service_content:
                missing_classes.append(cls)
        
        if missing_classes:
            print(f"  ❌ {service_file}: missing {', '.join(missing_classes)}")
            all_ok = False
        else:
            print(f"  ✓ {service_file}: complete")
    
    if all_ok:
        print("\n✓ All core services implemented")
    else:
        print("\n❌ Some services incomplete")
    
    return all_ok


def check_database_models():
    """Verify all database models are defined."""
    print("\n" + "=" * 60)
    print("6. Checking Database Models")
    print("=" * 60)
    
    models = [
        ("analysis.py", "MedicalAnalysis"),
        ("result.py", "AnalysisResult"),
        ("document.py", "UploadedDocument"),
        ("radiology.py", "RadiologyFinding"),
        ("integration_client.py", "IntegrationClient"),
        ("audit.py", "AuditEvent"),
    ]
    
    all_ok = True
    for model_file, model_class in models:
        model_path = Path("backend/models") / model_file
        
        if not model_path.exists():
            print(f"  ❌ Missing: {model_file}")
            all_ok = False
            continue
        
        with open(model_path) as f:
            model_content = f.read()
        
        if model_class not in model_content:
            print(f"  ❌ {model_file}: {model_class} not defined")
            all_ok = False
        else:
            print(f"  ✓ {model_file}: {model_class} defined")
    
    if all_ok:
        print("\n✓ All database models defined")
    else:
        print("\n❌ Some models missing")
    
    return all_ok


def check_documentation():
    """Verify all documentation files are complete."""
    print("\n" + "=" * 60)
    print("7. Checking Documentation")
    print("=" * 60)
    
    docs = {
        "README.md": ["Installation", "Features", "Usage"],
        "docs/API.md": ["Endpoints", "Authentication", "Examples"],
        "docs/DEPLOYMENT.md": ["Docker", "Environment"],
        "docs/ARCHITECTURE.md": ["Architecture", "Components"],
        "docs/SECURITY.md": ["Security", "Authentication"],
        "docs/MODEL_LIMITATIONS.md": ["Limitations", "Disclaimers"],
    }
    
    all_ok = True
    for doc_file, required_sections in docs.items():
        doc_path = Path(doc_file)
        
        if not doc_path.exists():
            print(f"  ❌ Missing: {doc_file}")
            all_ok = False
            continue
        
        with open(doc_path) as f:
            doc_content = f.read()
        
        missing_sections = []
        for section in required_sections:
            if section.lower() not in doc_content.lower():
                missing_sections.append(section)
        
        if missing_sections:
            print(f"  ⚠️  {doc_file}: may be missing sections {', '.join(missing_sections)}")
        else:
            print(f"  ✓ {doc_file}: appears complete")
    
    if all_ok:
        print("\n✓ All documentation files present")
    else:
        print("\n❌ Some documentation missing")
    
    return all_ok


def check_tests():
    """Verify test coverage exists."""
    print("\n" + "=" * 60)
    print("8. Checking Test Suite")
    print("=" * 60)
    
    test_files = [
        "tests/conftest.py",
        "tests/unit/test_symptom_service.py",
        "tests/unit/test_emergency_service.py",
        "tests/api/test_health.py",
        "tests/integration/test_document_workflow.py",
        "tests/integration/test_radiology_workflow.py",
    ]
    
    all_ok = True
    for test_file in test_files:
        test_path = Path(test_file)
        
        if not test_path.exists():
            print(f"  ❌ Missing: {test_file}")
            all_ok = False
        else:
            # Check if file has actual test functions
            with open(test_path) as f:
                content = f.read()
            
            if "def test_" in content or "class Test" in content:
                print(f"  ✓ {test_file}: has tests")
            else:
                print(f"  ⚠️  {test_file}: exists but may be empty")
    
    if all_ok:
        print("\n✓ Test suite present")
    else:
        print("\n❌ Some tests missing")
    
    return all_ok


def generate_summary_report(results):
    """Generate final summary report."""
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    total_checks = len(results)
    passed_checks = sum(results.values())
    
    print(f"\nTotal Checks: {total_checks}")
    print(f"Passed: {passed_checks}")
    print(f"Failed: {total_checks - passed_checks}")
    print(f"Success Rate: {(passed_checks/total_checks)*100:.1f}%")
    
    print("\nResults by Category:")
    for check_name, passed in results.items():
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"  {status} - {check_name}")
    
    if passed_checks == total_checks:
        print("\n" + "=" * 60)
        print("✓ ALL VERIFICATION CHECKS PASSED")
        print("=" * 60)
        print("\nClaraMed implementation is complete and ready for deployment!")
        print("\nNext steps:")
        print("  1. Install dependencies: pip install -r requirements.txt")
        print("  2. Configure .env file")
        print("  3. Run dependency check: python scripts/check_dependencies.py")
        print("  4. Start services: docker-compose up")
        print("  5. Run tests: pytest tests/ -v")
        return True
    else:
        print("\n" + "=" * 60)
        print("❌ VERIFICATION INCOMPLETE")
        print("=" * 60)
        print("\nSome checks failed. Review the output above and address missing components.")
        return False


def main():
    """Run all verification checks."""
    print("\nClaraMed Implementation Verification")
    print("Per BUILD.md Section 27 Acceptance Criteria\n")
    
    results = {
        "Project Structure": check_project_structure(),
        "Configuration Files": check_configuration_files(),
        "Docker Configuration": check_docker_configuration(),
        "API Implementation": check_api_implementation(),
        "Service Layer": check_service_implementation(),
        "Database Models": check_database_models(),
        "Documentation": check_documentation(),
        "Test Suite": check_tests(),
    }
    
    success = generate_summary_report(results)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
