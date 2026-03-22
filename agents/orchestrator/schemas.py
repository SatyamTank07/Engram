"""
Pydantic input schemas for the Orchestrator's tools.

Includes routing tool schemas (one per sub-agent) and cross-entity schemas.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Routing tool schemas — one per sub-agent
# ---------------------------------------------------------------------------
class RouteToAgentInput(BaseModel):
    task_description: str = Field(
        ...,
        description="Clear task description for the sub-agent. Be specific about what to create, search, update, or delete.",
    )


# ---------------------------------------------------------------------------
# Cross-entity tool schemas (same as backend/app/agent.py)
# ---------------------------------------------------------------------------
class LinkEntitiesInput(BaseModel):
    from_type: str = Field(..., description="Source entity type: Person, Idea, Content, or Project")
    from_id: str = Field(..., description="UUID of the source entity")
    to_type: str = Field(..., description="Target entity type: Person, Idea, Content, or Project")
    to_id: str = Field(..., description="UUID of the target entity")
    rel_type: str = Field(
        ...,
        description="Relationship type: THINKS, SHARED_BY, AUTHORED, RECOMMENDED, CONSUMED_WITH, WORKS_ON, COLLABORATES_ON, INSPIRED_BY, APPLIED_IN, REFERENCE_FOR",
    )
    properties: Optional[Dict[str, Any]] = Field(default=None, description="Optional properties for the relationship")


class GetEntityGraphInput(BaseModel):
    entity_type: str = Field(..., description="Entity type: Person, Idea, Content, or Project")
    entity_id: str = Field(..., description="UUID of the entity")
