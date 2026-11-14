"""
Helper script to encode DATABASE_URL with special characters in password.

Special characters in passwords must be URL-encoded:
@ -> %40
: -> %3A
/ -> %2F
? -> %3F
# -> %23
[ -> %5B
] -> %5D
% -> %25
"""
from urllib.parse import quote_plus
import sys

if len(sys.argv) < 2:
    print("Usage: python encode_database_url.py <password>")
    print("\nExample:")
    print('  python encode_database_url.py "my@password"')
    print("\nOutput:")
    print("  DATABASE_URL=postgresql://claramed:my%40password@localhost:5432/claramed")
    sys.exit(1)

password = sys.argv[1]
encoded_password = quote_plus(password)

database_url = f"postgresql://claramed:{encoded_password}@localhost:5432/claramed"

print(f"\nEncoded DATABASE_URL:")
print(database_url)

print(f"\nAdd this to your .env file:")
print(f'DATABASE_URL={database_url}')

# Test the connection
print("\nTesting connection...")
try:
    import psycopg2
    conn = psycopg2.connect(database_url)
    print("✓ Connection successful!")
    cursor = conn.cursor()
    cursor.execute("SELECT current_database(), current_user;")
    db, user = cursor.fetchone()
    print(f"  Database: {db}")
    print(f"  User: {user}")
    conn.close()
except Exception as e:
    print(f"✗ Connection failed: {e}")
    sys.exit(1)
