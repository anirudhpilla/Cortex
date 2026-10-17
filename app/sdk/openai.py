from functools import lru_cache
from langchain_openai import ChatOpenAI
from app.config import get_settings


@lru_cache
def get_model() -> ChatOpenAI:
    settings = get_settings()

    if not settings.openai_api_key:
        raise RuntimeError("OpenAI API key is not configured")

    return ChatOpenAI(
        model="gpt-4o-mini",
        api_key=settings.openai_api_key.get_secret_value(),
        temperature=0,
        timeout=30,
        max_retries=0,
    )
