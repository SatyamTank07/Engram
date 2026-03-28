"""
System prompt for the Idea sub-agent.
Rendered from Jinja2 template with dynamic context variables.
"""

from agents.common.prompt_loader import render_prompt

# Enum values injected into the template
IDEA_TYPES = ["prediction", "opinion", "decision", "question", "realization", "hypothesis", "lesson_learned"]
IDEA_STATUSES = ["active", "validated", "invalidated", "evolved", "abandoned"]

DEFAULT_TOOLS = [
    {"name": "create_idea", "description": "Create a new idea. Include all extractable fields."},
    {"name": "search_ideas", "description": "Semantic search by name/description. Always search before creating."},
    {"name": "list_ideas", "description": "List all ideas. Supports pagination and filters (idea_type, status, tags)."},
    {"name": "get_idea", "description": "Fetch full details by ID."},
    {"name": "update_idea", "description": "Modify idea fields."},
    {"name": "delete_idea", "description": "Remove an idea (only if user explicitly asks)."},
]


def get_idea_prompt(user_name: str | None = None, tools: list | None = None) -> str:
    """Render the idea agent system prompt with context variables."""
    return render_prompt(
        "idea_agent",
        user_name=user_name,
        tools=tools or DEFAULT_TOOLS,
        idea_types=IDEA_TYPES,
        idea_statuses=IDEA_STATUSES,
    )


# Backwards-compatible constant
IDEA_AGENT_PROMPT = get_idea_prompt()
