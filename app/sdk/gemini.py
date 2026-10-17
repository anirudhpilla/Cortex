from functools import lru_cache
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import get_settings

@lru_cache
def get_model() -> ChatGoogleGenerativeAI:
    settings = get_settings()

    if not settings.google_api_key:
        raise RuntimeError("Google API key is not configured")

    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.google_api_key.get_secret_value(),
        temperature=0,
        timeout=30,
        max_retries=0,
    )
