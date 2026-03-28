"""
LLM factory — creates the chat model based on environment configuration.
Extracted from backend/app/agent.py for reuse across all sub-agents.
"""

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_nvidia_ai_endpoints import ChatNVIDIA

from agents.common.config import (
    LLM_PROVIDER,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    GOOGLE_API_KEY,
    GOOGLE_MODEL,
    NVIDIA_API_KEY,
    NVIDIA_MODEL,
    NVIDIA_TEMPERATURE,
    NVIDIA_TOP_P,
    NVIDIA_MAX_TOKENS,
)


def _get_openai_llm():
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable is not set")
    return ChatOpenAI(model=OPENAI_MODEL, api_key=OPENAI_API_KEY)


def _get_google_llm():
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY environment variable is not set")
    return ChatGoogleGenerativeAI(model=GOOGLE_MODEL, google_api_key=GOOGLE_API_KEY)


def _get_nvidia_llm():
    if not NVIDIA_API_KEY:
        raise ValueError("NVIDIA_API_KEY environment variable is not set")
    return ChatNVIDIA(
        model=NVIDIA_MODEL,
        api_key=NVIDIA_API_KEY,
        temperature=NVIDIA_TEMPERATURE,
        top_p=NVIDIA_TOP_P,
        max_tokens=NVIDIA_MAX_TOKENS,
    )


def get_llm():
    """Initialize and return the LLM based on environment configuration."""
    providers = {
        "openai": _get_openai_llm,
        "google": _get_google_llm,
        "nvidia": _get_nvidia_llm,
    }
    if LLM_PROVIDER not in providers:
        raise ValueError(
            f"Unsupported LLM provider: {LLM_PROVIDER}. Supported: {list(providers.keys())}"
        )
    return providers[LLM_PROVIDER]()
