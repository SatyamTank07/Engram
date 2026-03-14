"""Tests for agent.py — Phase 5: Chat & Agent (Mock LLM)."""

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure env vars are set before importing agent
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key")
os.environ.setdefault("LLM_PROVIDER", "openai")

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.agent import (
    MAX_HISTORY_PAIRS,
    MAX_TOOL_ITERATIONS,
    SYSTEM_PROMPT,
    _make_tools,
    format_chat_history,
    get_agent_response,
    get_llm,
    stream_agent_response,
)


# ===================================================================
# format_chat_history
# ===================================================================
class TestFormatChatHistory:
    def test_empty_history(self):
        result = format_chat_history([])
        assert len(result) == 1
        assert isinstance(result[0], SystemMessage)
        assert result[0].content == SYSTEM_PROMPT

    def test_single_pair(self):
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        result = format_chat_history(messages)
        assert len(result) == 3  # system + 2
        assert isinstance(result[1], HumanMessage)
        assert isinstance(result[2], AIMessage)
        assert result[1].content == "Hello"
        assert result[2].content == "Hi!"

    def test_role_mapping(self):
        messages = [
            {"role": "user", "content": "A"},
            {"role": "assistant", "content": "B"},
            {"role": "user", "content": "C"},
        ]
        result = format_chat_history(messages)
        assert isinstance(result[1], HumanMessage)
        assert isinstance(result[2], AIMessage)
        assert isinstance(result[3], HumanMessage)

    def test_windowing_to_max_pairs(self):
        """History exceeding MAX_HISTORY_PAIRS * 2 messages should be trimmed."""
        messages = []
        for i in range(MAX_HISTORY_PAIRS + 5):
            messages.append({"role": "user", "content": f"Q{i}"})
            messages.append({"role": "assistant", "content": f"A{i}"})

        result = format_chat_history(messages)
        # system message + MAX_HISTORY_PAIRS * 2 messages
        assert len(result) == 1 + MAX_HISTORY_PAIRS * 2

    def test_windowing_keeps_most_recent(self):
        """Windowed messages should be the most recent ones."""
        messages = []
        for i in range(MAX_HISTORY_PAIRS + 3):
            messages.append({"role": "user", "content": f"Q{i}"})
            messages.append({"role": "assistant", "content": f"A{i}"})

        result = format_chat_history(messages)
        # The last user message in result should be the most recent
        last_user = [m for m in result if isinstance(m, HumanMessage)][-1]
        assert last_user.content == f"Q{MAX_HISTORY_PAIRS + 2}"

    def test_exact_window_size_no_trimming(self):
        """Exactly MAX_HISTORY_PAIRS pairs should not be trimmed."""
        messages = []
        for i in range(MAX_HISTORY_PAIRS):
            messages.append({"role": "user", "content": f"Q{i}"})
            messages.append({"role": "assistant", "content": f"A{i}"})

        result = format_chat_history(messages)
        assert len(result) == 1 + MAX_HISTORY_PAIRS * 2
        # First user message should be Q0
        assert result[1].content == "Q0"

    def test_unknown_role_ignored(self):
        """Messages with unknown roles should be skipped."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "system", "content": "Ignored"},
            {"role": "assistant", "content": "Hi!"},
        ]
        result = format_chat_history(messages)
        # system + user + assistant (system role in messages is not mapped)
        assert len(result) == 3


# ===================================================================
# _make_tools
# ===================================================================
class TestMakeTools:
    @patch("app.agent.MCP_TOOLS_AVAILABLE", True)
    def test_returns_10_tools(self):
        tools = _make_tools("user-123")
        assert len(tools) == 10

    @patch("app.agent.MCP_TOOLS_AVAILABLE", True)
    def test_tool_names(self):
        tools = _make_tools("user-123")
        names = {t.name for t in tools}
        expected = {
            "create_person", "get_person", "list_persons", "update_person",
            "delete_person", "search_person", "add_relationship",
            "get_relationships", "identify_face", "store_person_face",
        }
        assert names == expected

    @patch("app.agent.MCP_TOOLS_AVAILABLE", True)
    def test_user_id_binding(self):
        """Tools created for different user_ids should be separate instances."""
        tools_a = _make_tools("user-A")
        tools_b = _make_tools("user-B")
        # They should be distinct tool instances
        assert tools_a[0] is not tools_b[0]


# ===================================================================
# get_llm
# ===================================================================
class TestGetLLM:
    @patch.dict(os.environ, {"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "sk-test"})
    def test_openai_provider(self):
        llm = get_llm()
        assert "ChatOpenAI" in type(llm).__name__

    @patch.dict(os.environ, {"LLM_PROVIDER": "google", "GOOGLE_API_KEY": "test-key"})
    def test_google_provider(self):
        llm = get_llm()
        assert "Google" in type(llm).__name__

    @patch.dict(os.environ, {"LLM_PROVIDER": "unsupported"})
    def test_unsupported_provider_raises(self):
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            get_llm()

    @patch.dict(os.environ, {"LLM_PROVIDER": "openai", "OPENAI_API_KEY": ""}, clear=False)
    def test_missing_openai_key_raises(self):
        # Remove the key entirely
        env = os.environ.copy()
        env.pop("OPENAI_API_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                get_llm()

    @patch.dict(os.environ, {"LLM_PROVIDER": "google"}, clear=False)
    def test_missing_google_key_raises(self):
        env = os.environ.copy()
        env.pop("GOOGLE_API_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
                get_llm()


# ===================================================================
# get_agent_response
# ===================================================================
class TestGetAgentResponse:
    @pytest.mark.asyncio
    async def test_simple_response_no_tools(self):
        """LLM returns a plain text response (no tool calls)."""
        mock_response = MagicMock()
        mock_response.content = "Hello! How can I help?"
        mock_response.tool_calls = []

        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("app.agent.get_llm", return_value=mock_llm), \
             patch("app.agent.MCP_TOOLS_AVAILABLE", False):
            result = await get_agent_response("Hi", user_id="user-1")

        assert result == "Hello! How can I help?"

    @pytest.mark.asyncio
    async def test_image_url_prepended(self):
        """When image_url is provided, it should be prepended to the user message."""
        mock_response = MagicMock()
        mock_response.content = "I see an image."
        mock_response.tool_calls = []

        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("app.agent.get_llm", return_value=mock_llm), \
             patch("app.agent.MCP_TOOLS_AVAILABLE", False):
            result = await get_agent_response(
                "Who is this?", image_url="/uploads/chat/test.jpg", user_id="user-1"
            )

        # Check that the message passed to LLM contains image markers
        call_args = mock_llm.ainvoke.call_args[0][0]
        user_msg = call_args[-1]  # last message should be user's
        assert "[ATTACHED_IMAGE]" in user_msg.content
        assert "/uploads/chat/test.jpg" in user_msg.content

    @pytest.mark.asyncio
    async def test_tool_call_flow(self):
        """LLM makes a tool call, then produces a final text response."""
        # First invocation: LLM wants to call a tool
        tool_call_response = MagicMock()
        tool_call_response.tool_calls = [
            {"name": "search_person", "args": {"search_term": "John"}, "id": "call-1"}
        ]
        tool_call_response.content = ""

        # Second invocation: LLM produces final text
        final_response = MagicMock()
        final_response.tool_calls = []
        final_response.content = "I found John in the database."

        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_llm.ainvoke = AsyncMock(side_effect=[tool_call_response, final_response])

        # Mock the search_person tool
        mock_tool = MagicMock()
        mock_tool.name = "search_person"
        mock_tool.ainvoke = AsyncMock(return_value={"status": "success", "results": []})

        with patch("app.agent.get_llm", return_value=mock_llm), \
             patch("app.agent._make_tools", return_value=[mock_tool]), \
             patch("app.agent.MCP_TOOLS_AVAILABLE", True):
            result = await get_agent_response("Find John", user_id="user-1")

        assert result == "I found John in the database."
        mock_tool.ainvoke.assert_called_once_with({"search_term": "John"})

    @pytest.mark.asyncio
    async def test_tool_not_found(self):
        """When LLM requests an unknown tool, an error message is returned."""
        tool_call_response = MagicMock()
        tool_call_response.tool_calls = [
            {"name": "nonexistent_tool", "args": {}, "id": "call-1"}
        ]
        tool_call_response.content = ""

        final_response = MagicMock()
        final_response.tool_calls = []
        final_response.content = "I encountered an issue."

        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_llm.ainvoke = AsyncMock(side_effect=[tool_call_response, final_response])

        with patch("app.agent.get_llm", return_value=mock_llm), \
             patch("app.agent._make_tools", return_value=[]), \
             patch("app.agent.MCP_TOOLS_AVAILABLE", True):
            result = await get_agent_response("Do something", user_id="user-1")

        assert result == "I encountered an issue."

    @pytest.mark.asyncio
    async def test_tool_execution_error_handled(self):
        """Tool execution exceptions should be caught and reported to LLM."""
        tool_call_response = MagicMock()
        tool_call_response.tool_calls = [
            {"name": "create_person", "args": {"name": "Test"}, "id": "call-1"}
        ]
        tool_call_response.content = ""

        final_response = MagicMock()
        final_response.tool_calls = []
        final_response.content = "Sorry, I encountered an error."

        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_llm.ainvoke = AsyncMock(side_effect=[tool_call_response, final_response])

        mock_tool = MagicMock()
        mock_tool.name = "create_person"
        mock_tool.ainvoke = AsyncMock(side_effect=Exception("Neo4j connection failed"))

        with patch("app.agent.get_llm", return_value=mock_llm), \
             patch("app.agent._make_tools", return_value=[mock_tool]), \
             patch("app.agent.MCP_TOOLS_AVAILABLE", True):
            result = await get_agent_response("Create person Test", user_id="user-1")

        assert result == "Sorry, I encountered an error."

    @pytest.mark.asyncio
    async def test_max_iterations_limit(self):
        """Agent should stop after MAX_TOOL_ITERATIONS even if LLM keeps calling tools."""
        # All responses want to call tools
        tool_response = MagicMock()
        tool_response.tool_calls = [
            {"name": "search_person", "args": {"search_term": "loop"}, "id": "call-1"}
        ]
        tool_response.content = ""

        final_response = MagicMock()
        final_response.tool_calls = []
        final_response.content = "Reached limit."

        # MAX_TOOL_ITERATIONS + 1 tool responses, then final after limit message
        side_effects = [tool_response] * (MAX_TOOL_ITERATIONS + 1) + [final_response]

        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_llm.ainvoke = AsyncMock(side_effect=side_effects)

        mock_tool = MagicMock()
        mock_tool.name = "search_person"
        mock_tool.ainvoke = AsyncMock(return_value={"status": "ok"})

        with patch("app.agent.get_llm", return_value=mock_llm), \
             patch("app.agent._make_tools", return_value=[mock_tool]), \
             patch("app.agent.MCP_TOOLS_AVAILABLE", True):
            result = await get_agent_response("Loop forever", user_id="user-1")

        assert result == "Reached limit."

    @pytest.mark.asyncio
    async def test_api_key_error_wrapped_in_exception(self):
        """API key ValueError from get_llm should be caught and wrapped."""
        with patch("app.agent.get_llm", side_effect=ValueError("Invalid or missing API key")):
            with pytest.raises(Exception, match="Error getting response"):
                await get_agent_response("Hello")

    @pytest.mark.asyncio
    async def test_generic_error_raises_exception(self):
        """Non-API-key errors should be wrapped in a generic Exception."""
        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("Connection timeout"))

        with patch("app.agent.get_llm", return_value=mock_llm), \
             patch("app.agent.MCP_TOOLS_AVAILABLE", False):
            with pytest.raises(Exception, match="Error getting response"):
                await get_agent_response("Hello")

    @pytest.mark.asyncio
    async def test_no_tools_when_no_user_id(self):
        """Without user_id, tools should not be created."""
        mock_response = MagicMock()
        mock_response.content = "Response"
        mock_response.tool_calls = []

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch("app.agent.get_llm", return_value=mock_llm), \
             patch("app.agent.MCP_TOOLS_AVAILABLE", True), \
             patch("app.agent._make_tools") as mock_make:
            result = await get_agent_response("Hello", user_id=None)

        mock_make.assert_not_called()
        # llm should be called directly (not via bind_tools)
        mock_llm.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_history_passed_to_format(self):
        """Chat history should be properly formatted and included in messages."""
        mock_response = MagicMock()
        mock_response.content = "Got it."
        mock_response.tool_calls = []

        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        history = [
            {"role": "user", "content": "Previous Q"},
            {"role": "assistant", "content": "Previous A"},
        ]

        with patch("app.agent.get_llm", return_value=mock_llm), \
             patch("app.agent.MCP_TOOLS_AVAILABLE", False):
            await get_agent_response("New Q", chat_history=history)

        call_messages = mock_llm.ainvoke.call_args[0][0]
        # System + previous user + previous assistant + new user
        assert len(call_messages) == 4
        assert isinstance(call_messages[0], SystemMessage)
        assert call_messages[1].content == "Previous Q"
        assert call_messages[2].content == "Previous A"
        assert call_messages[3].content == "New Q"


# ===================================================================
# stream_agent_response
# ===================================================================
class TestStreamAgentResponse:
    @pytest.mark.asyncio
    async def test_yields_chunks(self):
        """Streaming should yield individual content chunks."""
        mock_response = MagicMock()
        mock_response.tool_calls = []
        mock_response.content = "Full response"

        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        # Simulate astream yielding chunks
        chunk1 = MagicMock()
        chunk1.content = "Hello "
        chunk2 = MagicMock()
        chunk2.content = "world"
        chunk3 = MagicMock()
        chunk3.content = ""  # empty chunk should be skipped

        async def mock_astream(messages):
            yield chunk1
            yield chunk2
            yield chunk3

        mock_llm.astream = mock_astream

        with patch("app.agent.get_llm", return_value=mock_llm), \
             patch("app.agent.MCP_TOOLS_AVAILABLE", False):
            chunks = []
            async for chunk in stream_agent_response("Hi", user_id="user-1"):
                chunks.append(chunk)

        assert chunks == ["Hello ", "world"]

    @pytest.mark.asyncio
    async def test_image_url_in_streaming(self):
        """Image URL should be prepended in streaming mode too."""
        mock_response = MagicMock()
        mock_response.tool_calls = []

        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        chunk = MagicMock()
        chunk.content = "I see it"

        async def mock_astream(messages):
            # Verify the user message contains image markers
            user_msg = messages[-1]
            assert "[ATTACHED_IMAGE]" in user_msg.content
            yield chunk

        mock_llm.astream = mock_astream

        with patch("app.agent.get_llm", return_value=mock_llm), \
             patch("app.agent.MCP_TOOLS_AVAILABLE", False):
            chunks = []
            async for c in stream_agent_response(
                "What's this?", image_url="/uploads/chat/img.jpg", user_id="user-1"
            ):
                chunks.append(c)

        assert "I see it" in chunks

    @pytest.mark.asyncio
    async def test_tool_calls_resolved_before_streaming(self):
        """Tool calls should be resolved non-streaming, then final response streamed."""
        # First ainvoke: tool call
        tool_call_response = MagicMock()
        tool_call_response.tool_calls = [
            {"name": "search_person", "args": {"search_term": "Alice"}, "id": "tc-1"}
        ]
        tool_call_response.content = ""

        # Second ainvoke: no more tool calls
        resolved_response = MagicMock()
        resolved_response.tool_calls = []
        resolved_response.content = "Found Alice."

        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_llm.ainvoke = AsyncMock(side_effect=[tool_call_response, resolved_response])

        chunk = MagicMock()
        chunk.content = "Found Alice."

        async def mock_astream(messages):
            yield chunk

        mock_llm.astream = mock_astream

        mock_tool = MagicMock()
        mock_tool.name = "search_person"
        mock_tool.ainvoke = AsyncMock(return_value={"results": [{"name": "Alice"}]})

        with patch("app.agent.get_llm", return_value=mock_llm), \
             patch("app.agent._make_tools", return_value=[mock_tool]), \
             patch("app.agent.MCP_TOOLS_AVAILABLE", True):
            chunks = []
            async for c in stream_agent_response("Find Alice", user_id="user-1"):
                chunks.append(c)

        assert "Found Alice." in chunks
        mock_tool.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_streaming_error_raises(self):
        """Errors during streaming should propagate."""
        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM down"))

        with patch("app.agent.get_llm", return_value=mock_llm), \
             patch("app.agent.MCP_TOOLS_AVAILABLE", False):
            with pytest.raises(Exception, match="Error getting response"):
                async for _ in stream_agent_response("Hi"):
                    pass

    @pytest.mark.asyncio
    async def test_streaming_api_key_error(self):
        """API key ValueError in streaming should be caught and wrapped."""
        with patch("app.agent.get_llm", side_effect=ValueError("Invalid or missing API key")):
            with pytest.raises(Exception, match="Error getting response"):
                async for _ in stream_agent_response("Hi"):
                    pass
