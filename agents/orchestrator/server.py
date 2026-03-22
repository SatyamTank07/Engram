"""
Orchestrator Agent — standalone A2A server (port 5000).

Receives user messages, routes to domain-specific sub-agents via A2A,
handles cross-entity linking, and composes final responses.

Usage:
    python -m agents.orchestrator.server
"""

import asyncio
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

from agents.common.config import ORCHESTRATOR_PORT
from agents.common.a2a_utils import (
    extract_user_id,
    extract_message_text,
    build_completed_task,
    build_failed_task,
)
from agents.common.db_clients import init_databases
from agents.orchestrator.router import route_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("orchestrator")

# ---------------------------------------------------------------------------
# Agent Card — describes the orchestrator's capabilities for A2A discovery
# ---------------------------------------------------------------------------
AGENT_CARD = AgentCard(
    name="Engram Orchestrator",
    description="Central orchestrator for the Engram personal knowledge management system. Routes requests to specialist agents for people, ideas, content, and projects.",
    url=f"http://localhost:{ORCHESTRATOR_PORT}",
    version="1.0.0",
    skills=[
        AgentSkill(
            name="Person Management",
            description="Manages people, contacts, relationships, and face recognition via the Person Agent.",
            examples=[
                "My friend Rahul works at Google",
                "Who is Priya?",
                "Show me all my contacts",
            ],
        ),
        AgentSkill(
            name="Idea Tracking",
            description="Manages ideas, predictions, opinions, and decisions via the Idea Agent.",
            examples=[
                "I think AI will replace 50% of data entry jobs by 2028",
                "Show me all my predictions",
            ],
        ),
        AgentSkill(
            name="Content Tracking",
            description="Manages books, articles, videos, podcasts via the Content Agent.",
            examples=[
                "I'm reading Atomic Habits by James Clear",
                "What books have I finished?",
            ],
        ),
        AgentSkill(
            name="Project Management",
            description="Manages projects, goals, and active work via the Project Agent.",
            examples=[
                "Working on a fitness goal to run a half marathon",
                "Show me my in-progress projects",
            ],
        ),
        AgentSkill(
            name="Cross-Entity Linking",
            description="Connects entities across domains — e.g., a person who recommended a book, or a project inspired by an idea.",
            examples=[
                "Rahul recommended Sapiens",
                "My fitness project was inspired by reading Atomic Habits",
            ],
        ),
    ],
)


# ---------------------------------------------------------------------------
# Orchestrator A2A Server
# ---------------------------------------------------------------------------
class OrchestratorAgent(A2AServer):
    """A2A server that routes messages to sub-agents via LLM-based routing."""

    def __init__(self):
        super().__init__(agent_card=AGENT_CARD)
        self._db_initialized = False

    async def _ensure_db(self):
        if not self._db_initialized:
            await init_databases()
            self._db_initialized = True

    async def _handle_task_async(self, task):
        await self._ensure_db()

        user_id = extract_user_id(task)
        if not user_id:
            return build_failed_task(task, "Missing user_id in message metadata")

        user_text = extract_message_text(task)
        if not user_text:
            return build_failed_task(task, "Empty message")

        logger.info("Orchestrator received: user_id=%s, text=%s", user_id, user_text[:80])

        try:
            response_text = await route_message(user_text, user_id)
            return build_completed_task(task, response_text)
        except Exception as e:
            logger.exception("Orchestrator error")
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
    logger.info("Starting Orchestrator Agent on port %d …", ORCHESTRATOR_PORT)
    agent = OrchestratorAgent()
    run_server(agent, host="0.0.0.0", port=ORCHESTRATOR_PORT)


if __name__ == "__main__":
    main()
