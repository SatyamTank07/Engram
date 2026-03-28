"""Tests for agent.py — multi-agent orchestrator path."""

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure env vars are set before importing agent
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key")
os.environ.setdefault("LLM_PROVIDER", "openai")

from app.agent import (
    get_agent_response,
    stream_agent_response,
)


# ===================================================================
# get_agent_response
# ===================================================================
class TestGetAgentResponse:
    @pytest.mark.asyncio
    async def test_routes_through_orchestrator(self):
        """Message should be routed through the orchestrator."""
        with patch("app.agent._route_via_orchestrator", new_callable=AsyncMock) as mock_orch:
            mock_orch.return_value = "Hello from orchestrator!"
            result, trace = await get_agent_response("Hi", user_id="user-1", user_name="Test")

        assert result == "Hello from orchestrator!"
        mock_orch.assert_called_once_with(
            "Hi", "user-1", user_name="Test", chat_history=[]
        )

    @pytest.mark.asyncio
    async def test_user_id_required(self):
        """Should raise ValueError when user_id is not provided."""
        with pytest.raises(ValueError, match="user_id is required"):
            await get_agent_response("Hello", user_id=None)

    @pytest.mark.asyncio
    async def test_image_url_prepended(self):
        """When image_url is provided, it should be prepended to the user message."""
        with patch("app.agent._route_via_orchestrator", new_callable=AsyncMock) as mock_orch:
            mock_orch.return_value = "I see an image."
            await get_agent_response(
                "Who is this?", image_url="/uploads/chat/test.jpg", user_id="user-1"
            )

        call_args = mock_orch.call_args
        user_msg = call_args[0][0]
        assert "[ATTACHED_IMAGE]" in user_msg
        assert "/uploads/chat/test.jpg" in user_msg

    @pytest.mark.asyncio
    async def test_chat_history_forwarded(self):
        """Chat history should be passed to the orchestrator."""
        history = [
            {"role": "user", "content": "Previous Q"},
            {"role": "assistant", "content": "Previous A"},
        ]

        with patch("app.agent._route_via_orchestrator", new_callable=AsyncMock) as mock_orch:
            mock_orch.return_value = "Got it."
            await get_agent_response("New Q", chat_history=history, user_id="user-1")

        mock_orch.assert_called_once_with(
            "New Q", "user-1", user_name=None, chat_history=history
        )

    @pytest.mark.asyncio
    async def test_orchestrator_error_raises(self):
        """Orchestrator errors should propagate as wrapped exceptions."""
        with patch("app.agent._route_via_orchestrator", new_callable=AsyncMock) as mock_orch:
            mock_orch.side_effect = RuntimeError("Connection timeout")
            with pytest.raises(Exception, match="Error getting response"):
                await get_agent_response("Hello", user_id="user-1")

    @pytest.mark.asyncio
    async def test_returns_trace(self):
        """Should return trace data from finalize_trace."""
        mock_trace = {"spans": [{"name": "test"}]}
        with patch("app.agent._route_via_orchestrator", new_callable=AsyncMock) as mock_orch, \
             patch("app.agent.finalize_trace", return_value=mock_trace):
            mock_orch.return_value = "Response"
            result, trace = await get_agent_response("Hi", user_id="user-1")

        assert trace == mock_trace


# ===================================================================
# stream_agent_response
# ===================================================================
class TestStreamAgentResponse:
    @pytest.mark.asyncio
    async def test_yields_chunks(self):
        """Streaming should yield response in chunks."""
        with patch("app.agent._route_via_orchestrator", new_callable=AsyncMock) as mock_orch:
            mock_orch.return_value = "Hello from the orchestrator!"
            chunks = []
            async for chunk in stream_agent_response("Hi", user_id="user-1"):
                chunks.append(chunk)

        combined = "".join(c for c in chunks if not c.startswith("__TRACE__:"))
        assert combined == "Hello from the orchestrator!"

    @pytest.mark.asyncio
    async def test_no_user_id_yields_error(self):
        """Without user_id, should yield error message."""
        chunks = []
        async for chunk in stream_agent_response("Hi", user_id=None):
            chunks.append(chunk)

        assert any("user_id is required" in c for c in chunks)

    @pytest.mark.asyncio
    async def test_image_url_in_streaming(self):
        """Image URL should be prepended in streaming mode too."""
        with patch("app.agent._route_via_orchestrator", new_callable=AsyncMock) as mock_orch:
            mock_orch.return_value = "I see it"
            chunks = []
            async for c in stream_agent_response(
                "What's this?", image_url="/uploads/chat/img.jpg", user_id="user-1"
            ):
                chunks.append(c)

        call_args = mock_orch.call_args
        user_msg = call_args[0][0]
        assert "[ATTACHED_IMAGE]" in user_msg

    @pytest.mark.asyncio
    async def test_streaming_error_yields_message(self):
        """Errors during streaming should yield an error message."""
        with patch("app.agent._route_via_orchestrator", new_callable=AsyncMock) as mock_orch:
            mock_orch.side_effect = RuntimeError("LLM down")
            chunks = []
            async for c in stream_agent_response("Hi", user_id="user-1"):
                chunks.append(c)

        assert any("error" in c.lower() for c in chunks)

    @pytest.mark.asyncio
    async def test_trace_yielded_at_end(self):
        """Trace data should be yielded as a special marker after text chunks."""
        mock_trace = {"spans": []}
        with patch("app.agent._route_via_orchestrator", new_callable=AsyncMock) as mock_orch, \
             patch("app.agent.finalize_trace", return_value=mock_trace):
            mock_orch.return_value = "Response"
            chunks = []
            async for c in stream_agent_response("Hi", user_id="user-1"):
                chunks.append(c)

        trace_chunks = [c for c in chunks if c.startswith("__TRACE__:")]
        assert len(trace_chunks) == 1
        assert json.loads(trace_chunks[0].replace("__TRACE__:", "")) == mock_trace
