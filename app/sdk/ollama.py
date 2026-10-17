from functools import lru_cache
from langchain_ollama import ChatOllama
from app.config import get_settings

@lru_cache
def get_model() -> ChatOllama:
    settings = get_settings()

    return ChatOllama(
        model=settings.ollama_chat_model,
        base_url=settings.ollama_base_url,
        temperature=0,
        num_predict=1200,
        format="json",
    )
