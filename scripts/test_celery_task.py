"""
Test Celery Task Execution
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

def test_celery_task():
    """Test submitting and executing a Celery task"""
    print("\n=== Celery Task Execution Test ===\n")
    
    # Test 1: Import Celery app
    print("1. Importing Celery app...")
    try:
        from backend.workers.celery_app import celery_app
        print("   ✓ Celery app imported")
    except Exception as e:
        print(f"   ✗ Failed to import: {e}")
        return False
    
    # Test 2: Create a simple test task
    print("\n2. Defining test task...")
    try:
        @celery_app.task(name='test_add')
        def add(x, y):
            return x + y
        
        print("   ✓ Test task defined")
    except Exception as e:
        print(f"   ✗ Failed to define task: {e}")
        return False
    
    # Test 3: Submit task
    print("\n3. Submitting task...")
    try:
        result = add.apply_async(args=[4, 6])
        print(f"   ✓ Task submitted: {result.id}")
    except Exception as e:
        print(f"   ✗ Failed to submit task: {e}")
        return False
    
    # Test 4: Check result
    print("\n4. Waiting for result (5s timeout)...")
    try:
        value = result.get(timeout=5)
        print(f"   ✓ Task completed: 4 + 6 = {value}")
        
        if value == 10:
            print("\n✓ Celery task execution successful!")
            return True
        else:
            print(f"\n✗ Unexpected result: {value}")
            return False
    except Exception as e:
        print(f"   ✗ Failed to get result: {e}")
        print("\n   Note: This is expected if no Celery worker is running.")
        print("   To start a worker, run: celery -A backend.workers.celery_app worker --pool=solo -l info")
        return False

if __name__ == "__main__":
    success = test_celery_task()
    
    if not success:
        print("\n" + "="*60)
        print("Worker Start Command:")
        print("="*60)
        print("celery -A backend.workers.celery_app worker --pool=solo -l info")
        print("="*60)
    
    sys.exit(0 if success else 1)
