"""
Idea Agent — standalone A2A server (port 5002).

Handles all idea-related operations: CRUD for ideas/thoughts/predictions.
Receives A2A messages from the orchestrator (or direct callers),
runs a LangChain agent with 6 idea tools, and returns the result.

Usage:
    python -m agents.idea_agent.server
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path
_project_root = str(Path(__file__).parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from python_a2a import (
    A2AServer,
    AgentCard,
    AgentSkill,
    TaskStatus,
    TaskState,
    run_server,
)
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

from agents.common.config import IDEA_AGENT_PORT, MAX_TOOL_ITERATIONS, MAX_HISTORY_PAIRS
from agents.common.llm_factory import get_llm
from agents.common.a2a_utils import (
    extract_user_id,
    extract_message_text,
    build_completed_task,
    build_failed_task,
)
from agents.common.db_clients import init_databases
from agents.idea_agent.system_prompt import IDEA_AGENT_PROMPT
from agents.idea_agent.tools import make_idea_tools

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("idea_agent")

# ---------------------------------------------------------------------------
# Agent Card — describes this agent's capabilities for A2A discovery
# ---------------------------------------------------------------------------
AGENT_CARD = AgentCard(
    name="Idea Management Agent",
    description="Manages ideas, thoughts, predictions, opinions, and decisions in the knowledge graph — create, search, update, delete, and track ideas.",
    url=f"http://localhost:{IDEA_AGENT_PORT}",
    version="1.0.0",
    skills=[
        AgentSkill(
            name="Idea Tracking",
            description="Create, search, update, and delete ideas with fields like type, confidence, status, evidence, and tags.",
            examples=[
                "I think AI will replace 50% of data entry jobs by 2028",
                "I've decided to switch to Python for backend work",
                "Show me all my active predictions",
            ],
        ),
        AgentSkill(
            name="Idea Evolution",
            description="Track how ideas evolve over time — validate, invalidate, add evidence, update confidence.",
            examples=[
                "Mark my AI prediction as validated",
                "Add evidence for my remote work hypothesis",
                "What ideas have I abandoned?",
            ],
        ),
    ],
)


# ---------------------------------------------------------------------------
# Idea Agent A2A Server
# ---------------------------------------------------------------------------
class IdeaAgent(A2AServer):
    """A2A server that runs a LangChain agent with 6 idea tools."""

    def __init__(self):
        super().__init__(agent_card=AGENT_CARD)
        self._db_initialized = False

    async def _ensure_db(self):
        if not self._db_initialized:
            await init_databases()
            self._db_initialized = True

    # -- async handler (called from sync handle_task) ----------------------
    async def _handle_task_async(self, task):
        await self._ensure_db()

        user_id = extract_user_id(task)
        if not user_id:
            return build_failed_task(task, "Missing user_id in message metadata")

        user_text = extract_message_text(task)
        if not user_text:
            return build_failed_task(task, "Empty message")

        logger.info("Idea agent received: user_id=%s, text=%s", user_id, user_text[:80])

        try:
            llm = get_llm()
            tools = make_idea_tools(user_id)
            llm_with_tools = llm.bind_tools(tools)

            messages = [
                SystemMessage(content=IDEA_AGENT_PROMPT),
                HumanMessage(content=user_text),
            ]

            response = await llm_with_tools.ainvoke(messages)

            # Tool-call loop
            iterations = 0
            while response.tool_calls and iterations < MAX_TOOL_ITERATIONS:
                iterations += 1
                messages.append(response)

                for tc in response.tool_calls:
                    selected = next((t for t in tools if t.name == tc["name"]), None)
                    if selected:
                        try:
                            result = await selected.ainvoke(tc["args"])
                            content = json.dumps(result)
                        except Exception as e:
                            logger.error("Tool %s failed: %s", tc["name"], e)
                            content = f"Error executing tool {tc['name']}: {e}"
                    else:
                        content = f"Error: Tool {tc['name']} not found"
                    messages.append(ToolMessage(content=content, tool_call_id=tc["id"]))

                response = await llm_with_tools.ainvoke(messages)

            # If we hit the iteration cap, force a summary
            if iterations >= MAX_TOOL_ITERATIONS and response.tool_calls:
                logger.warning("Idea agent hit max tool iterations (%d)", MAX_TOOL_ITERATIONS)
                messages.append(response)
                for tc in response.tool_calls:
                    messages.append(
                        ToolMessage(
                            content="Error: Max tool iterations reached. Summarize and respond.",
                            tool_call_id=tc["id"],
                        )
                    )
                response = await llm_with_tools.ainvoke(messages)

            return build_completed_task(task, response.content)

        except Exception as e:
            logger.exception("Idea agent error")
            return build_failed_task(task, str(e))

    # -- sync entry point required by A2AServer ----------------------------
    def handle_task(self, task):
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self._handle_task_async(task))
                return future.result()
        return loop.run_until_complete(self._handle_task_async(task))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    logger.info("Starting Idea Agent on port %d …", IDEA_AGENT_PORT)
    agent = IdeaAgent()
    run_server(agent, host="0.0.0.0", port=IDEA_AGENT_PORT)


if __name__ == "__main__":
    main()
