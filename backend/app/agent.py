"""
Agent entry point for chat completions.

Routes all requests through the multi-agent orchestrator.
"""

import logging
import os
import sys
import json
from pathlib import Path

from backend.app.tracing import start_trace, finalize_trace

logger = logging.getLogger(__name__)

# Add project root to path to allow importing agents package
sys.path.append(str(Path(__file__).parent.parent.parent))


# ---------------------------------------------------------------------------
# In-process orchestrator bridge
# ---------------------------------------------------------------------------
async def _route_via_orchestrator(
    user_message: str,
    user_id: str,
    user_name: str | None = None,
    chat_history: list[dict] | None = None,
) -> str:
    """Route a message through the in-process orchestrator and return the response."""
    from agents.orchestrator.router import route_message
    from agents.common.db_clients import init_databases

    await init_databases()
    return await route_message(user_message, user_id, user_name=user_name, chat_history=chat_history)


def _get_trace_result() -> dict | None:
    """Finalize and return the current trace, if any."""
    return finalize_trace()


# ---------------------------------------------------------------------------
# Main agent entry point
# ---------------------------------------------------------------------------
async def get_agent_response(
    user_message: str,
    chat_history: list[dict] = None,
    image_url: str | None = None,
    user_id: str | None = None,
    user_name: str | None = None,
) -> str:
    """
    Get a response from the AI agent (async).

    Returns:
        A tuple of (response_text, trace_dict_or_None).

    Args:
        user_message: The user's input message
        chat_history: List of previous messages [{"role": "user"|"assistant", "content": "..."}]
        image_url: Optional URL of an uploaded image attached to this message
        user_id: Authenticated user's ID — used to scope all tool operations
        user_name: Authenticated user's display name — injected into the system prompt
    """
    if chat_history is None:
        chat_history = []

    if not user_id:
        raise ValueError("user_id is required")

    if image_url:
        user_message = f"[ATTACHED_IMAGE]\nImage URL: {image_url}\n[/ATTACHED_IMAGE]\n\n{user_message}"

    start_trace()

    try:
        logger.info("Routing through in-process orchestrator")
        response_text = await _route_via_orchestrator(
            user_message, user_id, user_name=user_name, chat_history=chat_history
        )
        return response_text, _get_trace_result()
    except Exception as e:
        logger.error("Orchestrator call failed: %s", e, exc_info=True)
        _get_trace_result()  # cleanup
        raise Exception(f"Error getting response: {e}")


async def stream_agent_response(
    user_message: str,
    chat_history: list[dict] = None,
    image_url: str | None = None,
    user_id: str | None = None,
    user_name: str | None = None,
):
    """
    Async generator that yields text chunks from the AI agent.

    The orchestrator response is fetched in full, then chunked for
    streaming compatibility. After all text chunks, yields a special
    ``__TRACE__:`` prefixed line containing JSON-serialized trace data.
    """
    if chat_history is None:
        chat_history = []

    if not user_id:
        yield "\n\nError: user_id is required for processing."
        return

    if image_url:
        user_message = f"[ATTACHED_IMAGE]\nImage URL: {image_url}\n[/ATTACHED_IMAGE]\n\n{user_message}"

    start_trace()

    try:
        logger.info("Streaming: routing through in-process orchestrator")
        response_text = await _route_via_orchestrator(
            user_message, user_id, user_name=user_name, chat_history=chat_history
        )
        # Yield the complete response in chunks for streaming compatibility
        chunk_size = 20
        for i in range(0, len(response_text), chunk_size):
            yield response_text[i:i + chunk_size]
        # Yield trace as a special marker
        trace_data = _get_trace_result()
        if trace_data:
            yield f"__TRACE__:{json.dumps(trace_data)}"
    except Exception as e:
        logger.error("Orchestrator streaming call failed: %s", e, exc_info=True)
        _get_trace_result()  # cleanup
        yield "\n\nI encountered an error while processing your request. Please try again."
