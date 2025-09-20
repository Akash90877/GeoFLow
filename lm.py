import os
import google.generativeai as genai

# Your API key must be set as an environment variable
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Check for the API key
if not os.getenv("GEMINI_API_KEY"):
    raise ValueError("GEMINI_API_KEY environment variable not set.")

# Get and print all models that support the generate_content method
print("Available Gemini models supporting text generation:")
for model in genai.list_models():
    if 'generateContent' in model.supported_generation_methods:
        print(f"Model Name: {model.name}")