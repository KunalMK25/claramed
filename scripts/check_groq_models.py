"""Check available Groq models."""
from groq import Groq
from backend.core.config import settings

print("Checking available Groq models...")
print(f"API Key configured: Yes (length {len(settings.GROQ_API_KEY)})")

try:
    client = Groq(api_key=settings.GROQ_API_KEY)
    
    # Try to list models
    models = client.models.list()
    
    print("\nAvailable models:")
    for model in models.data:
        print(f"  - {model.id}")
        if hasattr(model, 'owned_by'):
            print(f"    Owner: {model.owned_by}")
    
except Exception as e:
    print(f"Error: {e}")
    print("\nTrying common Groq model names:")
    common_models = [
        "llama3-8b-8192",
        "llama3-70b-8192", 
        "mixtral-8x7b-32768",
        "gemma-7b-it",
        "llama-3.1-8b-instant",
        "llama-3.1-70b-versatile"
    ]
    for model in common_models:
        print(f"  - {model}")
