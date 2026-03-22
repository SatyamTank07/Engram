"""
Agent network — in-process dispatch to sub-agents.

Instead of making HTTP calls to separate A2A containers, this module
runs each sub-agent's LangChain tool-loop directly in the same process.
"""

import json
import logging
import time
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from agents.common.config import MAX_TOOL_ITERATIONS
from agents.common.llm_factory import get_llm
from backend.app.tracing import start_agent_span, end_agent_span, log_tool_call

# Sub-agent tool factories + system prompts
from agents.person_agent.tools import make_person_tools
from agents.person_agent.system_prompt import PERSON_AGENT_PROMPT

from agents.idea_agent.tools import make_idea_tools
from agents.idea_agent.system_prompt import IDEA_AGENT_PROMPT

from agents.content_agent.tools import make_content_tools
from agents.content_agent.system_prompt import CONTENT_AGENT_PROMPT

from agents.project_agent.tools import make_project_tools
from agents.project_agent.system_prompt import PROJECT_AGENT_PROMPT

logger = logging.getLogger(__name__)

# Registry: agent name → (tool factory, system prompt)
AGENT_REGISTRY = {
    "person_agent": (make_person_tools, PERSON_AGENT_PROMPT),
    "idea_agent": (make_idea_tools, IDEA_AGENT_PROMPT),
    "content_agent": (make_content_tools, CONTENT_AGENT_PROMPT),
    "project_agent": (make_project_tools, PROJECT_AGENT_PROMPT),
}


async def _run_agent_loop(tools: List, system_prompt: str, user_text: str, agent_name: str = "sub_agent") -> str:
    """Run a LangChain agent tool-loop and return the final response text."""
    llm = get_llm()
    llm_with_tools = llm.bind_tools(tools)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_text),
    ]

    start_agent_span(agent_name)
    response = await llm_with_tools.ainvoke(messages)

    iterations = 0
    while response.tool_calls and iterations < MAX_TOOL_ITERATIONS:
        iterations += 1
        messages.append(response)

        for tc in response.tool_calls:
            selected = next((t for t in tools if t.name == tc["name"]), None)
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
        logger.warning("Agent hit max tool iterations (%d)", MAX_TOOL_ITERATIONS)
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


async def send_to_agent(agent_name: str, task_text: str, user_id: str, user_name: str | None = None) -> str:
    """Dispatch a task to a sub-agent in-process and return the response text.

    Args:
        agent_name: Key in AGENT_REGISTRY (e.g. "person_agent").
        task_text: The natural-language task description for the sub-agent.
        user_id: Authenticated user ID — passed to tool factories.
        user_name: Authenticated user's display name — injected into system prompt.

    Returns:
        The text response from the sub-agent, or an error string.
    """
    entry = AGENT_REGISTRY.get(agent_name)
    if not entry:
        return f"Error: Unknown agent '{agent_name}'"

    make_tools, system_prompt = entry

    # Inject user name into system prompt so sub-agent knows who "I/me/my" refers to
    if user_name:
        system_prompt = f"\n\nUSER IDENTITY: The user's name is {user_name}. When they say 'I', 'me', 'my', 'mine', they refer to {user_name}. Use '{user_name}' as the relationship_with value when the user mentions their own relationships." + system_prompt

    try:
        tools = make_tools(user_id)
        return await _run_agent_loop(tools, system_prompt, task_text, agent_name=agent_name)
    except Exception as e:
        logger.exception("Failed to run %s", agent_name)
        return f"Error calling {agent_name}: {e}"
