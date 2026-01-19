import google.generativeai as genai
from config import GOOGLE_API_KEY

genai.configure(api_key=GOOGLE_API_KEY)

models = genai.list_models()

for m in models:
    print(m.name, "→ supports:", m.supported_generation_methods)
