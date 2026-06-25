import os
import sys

# Ensure backend directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from app.core.config import settings
    import google.generativeai as genai
    from google.generativeai.types import GenerationConfig
except ImportError as e:
    print("FAILED")
    print(f"Error importing modules: {e}")
    sys.exit(1)

def test_gemini():
    api_key = settings.GEMINI_API_KEY.strip()
    if not api_key:
        print("FAILED")
        print("Error: GEMINI_API_KEY is not configured or is empty.")
        sys.exit(1)
        
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)
        
        config = GenerationConfig(
            temperature=0.0,
            max_output_tokens=50
        )
        response = model.generate_content("Say hello", generation_config=config)
        
        if response.text:
            print("SUCCESS")
            print(f"Response: {response.text.strip()}")
        else:
            print("FAILED")
            print("Error: Empty response returned from Gemini.")
            sys.exit(1)
    except Exception as e:
        print("FAILED")
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_gemini()
