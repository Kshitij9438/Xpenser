import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

def get_env_var(name: str) -> str:
    """Get environment variable or raise a clear error if missing."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"❌ Missing required environment variable: {name}\n"
            f"👉 Did you copy .env.example to .env and fill in your keys?"
        )
    return value

# Example usage
GOOGLE_API_KEY = get_env_var("GOOGLE_API_KEY")

# Optional vars (with defaults)
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
PORT = int(os.getenv("PORT", "8000"))

DATABASE_URL = get_env_var("DATABASE_URL")