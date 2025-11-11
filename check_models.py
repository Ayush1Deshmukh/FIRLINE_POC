import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Get the key
API_KEY = os.environ.get("GOOGLE_API_KEY")

if not API_KEY:
    print("Error: GOOGLE_API_KEY not found in your .env file.")
    exit()

try:
    genai.configure(api_key=API_KEY)

    print("--- 🔍 Finding available models for your API key... ---")
    found_models = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"✅ Found usable model: {m.name}")
            found_models.append(m.name)

    if not found_models:
        print("\n❌ No models found that support 'generateContent'.")
        print("Please check your Google AI Studio project and ensure the Generative Language API is enabled.")
    else:
        print("\n--- Recommendation ---")
        print("Please copy one of the model names above (e.g., 'models/gemini-1.5-flash-latest')")
        print("and paste it into the 'model_name' field in src/activities.py.")

except Exception as e:
    print(f"\n--- ❌ An error occurred ---")
    print(f"Error details: {e}")
    print("Please double-check that your GOOGLE_API_KEY is correct and valid.")