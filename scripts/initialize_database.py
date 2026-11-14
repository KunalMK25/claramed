"""
Initialize ClaraMed Database
Creates all tables using Alembic migrations
"""
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

def test_connection():
    """Test database connection"""
    print("Testing PostgreSQL connection...")
    try:
        import psycopg2
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"✓ Connected to: {version.split(',')[0]}")
        
        cursor.execute("SELECT current_user, current_database();")
        user, db = cursor.fetchone()
        print(f"✓ User: {user}, Database: {db}")
        
        conn.close()
        return True
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print("\nPlease run: .\\scripts\\reset_postgres_password.ps1")
        return False

def check_migrations_exist():
    """Check if migrations have been generated"""
    versions_dir = Path("migrations/versions")
    if not versions_dir.exists():
        print(f"\nCreating migrations/versions directory...")
        versions_dir.mkdir(parents=True, exist_ok=True)
        return False
    
    migrations = list(versions_dir.glob("*.py"))
    return len(migrations) > 0

def generate_initial_migration():
    """Generate initial Alembic migration"""
    print("\nGenerating initial migration...")
    
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "revision", "--autogenerate", "-m", "Initial schema"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✓ Migration generated successfully")
        print(result.stdout)
        return True
    else:
        print(f"✗ Migration generation failed:")
        print(result.stderr)
        return False

def apply_migrations():
    """Apply Alembic migrations"""
    print("\nApplying migrations...")
    
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✓ Migrations applied successfully")
        print(result.stdout)
        return True
    else:
        print(f"✗ Migration application failed:")
        print(result.stderr)
        return False

def verify_schema():
    """Verify database schema"""
    print("\nVerifying database schema...")
    try:
        from backend.database.connection import Base, engine
        from sqlalchemy import inspect
        
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        expected_tables = [
            'medical_analyses',
            'uploaded_documents',
            'analysis_results',
            'radiology_findings',
            'integration_clients',
            'audit_events',
            'alembic_version',
        ]
        
        print("\nDatabase tables:")
        for table in tables:
            status = "✓" if table in expected_tables else "?"
            print(f"  {status} {table}")
        
        missing = set(expected_tables) - set(tables) - {'alembic_version'}
        if missing:
            print(f"\n⚠ Missing tables: {missing}")
            return False
        
        print("\n✓ All expected tables exist")
        return True
    except Exception as e:
        print(f"✗ Schema verification failed: {e}")
        return False

def show_current_revision():
    """Show current Alembic revision"""
    print("\nChecking Alembic revision...")
    
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print(result.stdout)
    else:
        print("No migrations applied yet")

def main():
    """Main initialization workflow"""
    print("="*60)
    print("ClaraMed Database Initialization")
    print("="*60)
    print()
    
    # Step 1: Test connection
    if not test_connection():
        return False
    
    # Step 2: Check if migrations exist
    migrations_exist = check_migrations_exist()
    
    if not migrations_exist:
        print("\n⚠ No migrations found. Generating initial migration...")
        if not generate_initial_migration():
            return False
    else:
        print("\n✓ Migrations already exist")
    
    # Step 3: Show current revision
    show_current_revision()
    
    # Step 4: Apply migrations
    if not apply_migrations():
        return False
    
    # Step 5: Verify schema
    if not verify_schema():
        return False
    
    # Step 6: Show final revision
    show_current_revision()
    
    print("\n" + "="*60)
    print("✓ Database initialization complete!")
    print("="*60)
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
