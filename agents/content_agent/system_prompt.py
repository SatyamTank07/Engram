"""
System prompt for the Content sub-agent.
Rendered from Jinja2 template with dynamic context variables.
"""

from agents.common.prompt_loader import render_prompt

# Enum values injected into the template
CONTENT_TYPES = ["book", "article", "video", "podcast", "paper", "course", "movie", "tweet", "talk"]
CONTENT_STATUSES = ["want", "reading", "completed", "abandoned"]

DEFAULT_TOOLS = [
    {"name": "create_content", "description": "Create new content. Include all extractable fields."},
    {"name": "search_content", "description": "Semantic search by title/description. Always search before creating."},
    {"name": "list_content", "description": "List all content. Supports pagination and filters (content_type, status, tags)."},
    {"name": "get_content", "description": "Fetch full details by ID."},
    {"name": "update_content", "description": "Modify content fields."},
    {"name": "delete_content", "description": "Remove content (only if user explicitly asks)."},
]


def get_content_prompt(user_name: str | None = None, tools: list | None = None) -> str:
    """Render the content agent system prompt with context variables."""
    return render_prompt(
        "content_agent",
        user_name=user_name,
        tools=tools or DEFAULT_TOOLS,
        content_types=CONTENT_TYPES,
        content_statuses=CONTENT_STATUSES,
    )


# Backwards-compatible constant
CONTENT_AGENT_PROMPT = get_content_prompt()
