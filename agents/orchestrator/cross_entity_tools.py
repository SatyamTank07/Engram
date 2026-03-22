"""
Cross-entity LangChain tools for the Orchestrator.

These 2 tools (link_entities, get_entity_graph) span domains and live
on the orchestrator rather than any single sub-agent.
"""

import sys
from pathlib import Path
from typing import Any, Dict, Optional

from langchain_core.tools import tool

_project_root = str(Path(__file__).parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from mcp_server.tools import link_entities_tool, get_entity_graph_tool
from agents.orchestrator.schemas import LinkEntitiesInput, GetEntityGraphInput


def make_cross_entity_tools(user_id: str):
    """Return 2 LangChain tools for cross-entity operations, bound to user_id."""

    @tool(args_schema=LinkEntitiesInput)
    async def link_entities(
        from_type: str,
        from_id: str,
        to_type: str,
        to_id: str,
        rel_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """Create a cross-domain relationship between any two entities (Person, Idea, Content, Project). Use after sub-agents return entity IDs. Relationship types: THINKS, SHARED_BY, AUTHORED, RECOMMENDED, CONSUMED_WITH, WORKS_ON, COLLABORATES_ON, INSPIRED_BY, APPLIED_IN, REFERENCE_FOR. Example: Person 'Rahul' RECOMMENDED Content 'Sapiens'. Returns: {success, message, link: {from, to, type}}"""
        return await link_entities_tool(
            user_id,
            from_type=from_type,
            from_id=from_id,
            to_type=to_type,
            to_id=to_id,
            rel_type=rel_type,
            properties=properties,
        )

    @tool(args_schema=GetEntityGraphInput)
    async def get_entity_graph(entity_type: str, entity_id: str) -> dict:
        """Get ALL cross-domain connections of any entity. Shows how a Person/Idea/Content/Project is linked to other entities across domains. Use to answer questions like 'What did Rahul recommend?' or 'Who is working on this project?'. Returns: {success, entity: {id, name, type}, connections: [{related_entity, rel_type, direction}]}"""
        return await get_entity_graph_tool(user_id, entity_type=entity_type, entity_id=entity_id)

    return [link_entities, get_entity_graph]
