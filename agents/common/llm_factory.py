"""
LLM factory — creates the chat model based on environment configuration.
Extracted from backend/app/agent.py for reuse across all sub-agents.
"""

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

from agents.common.config import (
    LLM_PROVIDER,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    GOOGLE_API_KEY,
    GOOGLE_MODEL,
)


def _get_openai_llm():
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable is not set")
    return ChatOpenAI(model=OPENAI_MODEL, api_key=OPENAI_API_KEY)


def _get_google_llm():
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY environment variable is not set")
    return ChatGoogleGenerativeAI(model=GOOGLE_MODEL, google_api_key=GOOGLE_API_KEY)


def get_llm():
    """Initialize and return the LLM based on environment configuration."""
    providers = {
        "openai": _get_openai_llm,
        "google": _get_google_llm,
    }
    if LLM_PROVIDER not in providers:
        raise ValueError(
            f"Unsupported LLM provider: {LLM_PROVIDER}. Supported: {list(providers.keys())}"
        )
    return providers[LLM_PROVIDER]()
