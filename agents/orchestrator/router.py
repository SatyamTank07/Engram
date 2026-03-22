"""
LLM-based router for the Orchestrator Agent.

The orchestrator LLM gets 6 tools:
  - 4 routing tools (send_to_person_agent, send_to_idea_agent, etc.)
  - 2 cross-entity tools (link_entities, get_entity_graph)

The LLM decides which agent(s) to call, dispatches in-process,
and composes a final response from sub-agent results.
"""

import json
import logging
import sys
import time
from pathlib import Path

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

# Ensure project root is on sys.path
_project_root = str(Path(__file__).parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from agents.common.config import MAX_TOOL_ITERATIONS
from agents.common.llm_factory import get_llm
from backend.app.tracing import start_agent_span, end_agent_span, log_tool_call
from agents.orchestrator.system_prompt import get_orchestrator_prompt
from agents.orchestrator.schemas import RouteToAgentInput
from agents.orchestrator.agent_network import send_to_agent
from agents.orchestrator.cross_entity_tools import make_cross_entity_tools

logger = logging.getLogger(__name__)


def make_routing_tools(user_id: str, user_name: str | None = None):
    """Create 4 routing tools that dispatch to sub-agents via A2A."""

    @tool(args_schema=RouteToAgentInput)
    async def send_to_person_agent(task_description: str) -> str:
        """Route a task to the Person Agent. Use for anything about people, contacts, relationships, faces."""
        return await send_to_agent("person_agent", task_description, user_id, user_name=user_name)

    @tool(args_schema=RouteToAgentInput)
    async def send_to_idea_agent(task_description: str) -> str:
        """Route a task to the Idea Agent. Use for thoughts, predictions, opinions, decisions, hypotheses."""
        return await send_to_agent("idea_agent", task_description, user_id)

    @tool(args_schema=RouteToAgentInput)
    async def send_to_content_agent(task_description: str) -> str:
        """Route a task to the Content Agent. Use for books, articles, videos, podcasts, courses, ratings."""
        return await send_to_agent("content_agent", task_description, user_id)

    @tool(args_schema=RouteToAgentInput)
    async def send_to_project_agent(task_description: str) -> str:
        """Route a task to the Project Agent. Use for projects, goals, side projects, deadlines, priorities."""
        return await send_to_agent("project_agent", task_description, user_id)

    return [
        send_to_person_agent,
        send_to_idea_agent,
        send_to_content_agent,
        send_to_project_agent,
    ]


async def route_message(
    user_text: str,
    user_id: str,
    user_name: str | None = None,
    chat_history: list[dict] | None = None,
) -> str:
    """Route a user message through the orchestrator LLM.

    The LLM decides which sub-agent(s) to call, executes them via tool calls,
    optionally links entities, and composes a final response.

    Args:
        user_text: The user's natural-language message.
        user_id: Authenticated user ID.
        user_name: Authenticated user's display name.
        chat_history: Previous messages for conversation context.

    Returns:
        The orchestrator's final response text.
    """
    from langchain_core.messages import AIMessage

    llm = get_llm()

    # Build tool list: 4 routing + 2 cross-entity
    routing_tools = make_routing_tools(user_id, user_name=user_name)
    cross_entity_tools = make_cross_entity_tools(user_id)
    all_tools = routing_tools + cross_entity_tools
    tool_map = {t.name: t for t in all_tools}

    llm_with_tools = llm.bind_tools(all_tools)

    # Render orchestrator prompt with user context via Jinja2
    prompt = get_orchestrator_prompt(user_name=user_name)

    messages = [SystemMessage(content=prompt)]

    # Include conversation history so the orchestrator has context
    if chat_history:
        # Window: keep last 10 pairs (20 messages) to avoid token overflow
        window_size = 20
        windowed = chat_history[-window_size:] if len(chat_history) > window_size else chat_history
        for msg in windowed:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))

    messages.append(HumanMessage(content=user_text))

    start_agent_span("orchestrator")
    response = await llm_with_tools.ainvoke(messages)

    # Tool-call loop
    iterations = 0
    while response.tool_calls and iterations < MAX_TOOL_ITERATIONS:
        iterations += 1
        messages.append(response)

        for tc in response.tool_calls:
            selected = tool_map.get(tc["name"])
            t0 = time.time()
            tool_error = None
            tool_result = None
            if selected:
                try:
                    tool_result = await selected.ainvoke(tc["args"])
                    content = json.dumps(tool_result) if isinstance(tool_result, dict) else str(tool_result)
                except Exception as e:
                    logger.error("Tool %s failed: %s", tc["name"], e)
                    tool_error = str(e)
                    content = f"Error executing tool {tc['name']}: {e}"
            else:
                tool_error = f"Tool {tc['name']} not found"
                content = f"Error: Tool {tc['name']} not found"
            log_tool_call(tc["name"], tc["args"], tool_result, tool_error, (time.time() - t0) * 1000)
            messages.append(ToolMessage(content=content, tool_call_id=tc["id"]))

        response = await llm_with_tools.ainvoke(messages)

    # If we hit the iteration cap, force a summary
    if iterations >= MAX_TOOL_ITERATIONS and response.tool_calls:
        logger.warning("Orchestrator hit max tool iterations (%d)", MAX_TOOL_ITERATIONS)
        messages.append(response)
        for tc in response.tool_calls:
            messages.append(
                ToolMessage(
                    content="Error: Max tool iterations reached. Summarize and respond.",
                    tool_call_id=tc["id"],
                )
            )
        response = await llm_with_tools.ainvoke(messages)

    end_agent_span()
    return response.content
