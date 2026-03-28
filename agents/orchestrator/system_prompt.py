"""
System prompt for the Orchestrator Agent.
Rendered from Jinja2 template with dynamic context variables.
"""

from agents.common.prompt_loader import render_prompt

# Agent registry metadata for the template
AGENT_DEFINITIONS = [
    {
        "name": "person_agent",
        "display_name": "Person Agent",
        "description": "Manages people (friends, colleagues, family, contacts).",
        "route_keywords": "names, relationships, contacts, occupations, bios, face photos",
    },
    {
        "name": "idea_agent",
        "display_name": "Idea Agent",
        "description": "Manages thoughts, predictions, opinions, decisions, hypotheses.",
        "route_keywords": "ideas, predictions, opinions, decisions, questions, realizations",
    },
    {
        "name": "content_agent",
        "display_name": "Content Agent",
        "description": "Manages consumed content (books, articles, videos, podcasts, courses).",
        "route_keywords": "books, articles, videos, podcasts, reading lists, recommendations, ratings",
    },
    {
        "name": "project_agent",
        "display_name": "Project Agent",
        "description": "Manages goals, projects, active work.",
        "route_keywords": "projects, goals, side projects, health goals, career plans, deadlines",
    },
]

CROSS_ENTITY_TOOLS = [
    {"name": "link_entities", "description": "Connect any two entities across domains (e.g., Person->Content via RECOMMENDED)."},
    {"name": "get_entity_graph", "description": "See all connections of any entity."},
]

CROSS_ENTITY_REL_TYPES = [
    "THINKS", "SHARED_BY", "AUTHORED", "RECOMMENDED", "CONSUMED_WITH",
    "WORKS_ON", "COLLABORATES_ON", "INSPIRED_BY", "APPLIED_IN", "REFERENCE_FOR",
]


def get_orchestrator_prompt(
    user_name: str | None = None,
    agents: list | None = None,
    cross_entity_tools: list | None = None,
) -> str:
    """Render the orchestrator system prompt with context variables."""
    return render_prompt(
        "orchestrator",
        user_name=user_name,
        agents=agents or AGENT_DEFINITIONS,
        cross_entity_tools=cross_entity_tools or CROSS_ENTITY_TOOLS,
        cross_entity_rel_types=CROSS_ENTITY_REL_TYPES,
    )


# Backwards-compatible constant
ORCHESTRATOR_PROMPT = get_orchestrator_prompt()
