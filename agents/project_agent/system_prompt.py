"""
System prompt for the Project sub-agent.
Rendered from Jinja2 template with dynamic context variables.
"""

from agents.common.prompt_loader import render_prompt

# Enum values injected into the template
PROJECT_TYPES = ["work", "side_project", "learning", "health", "financial", "travel", "creative", "career"]
PROJECT_STATUSES = ["idea", "planned", "in_progress", "paused", "completed", "abandoned"]

DEFAULT_TOOLS = [
    {"name": "create_project", "description": "Create a new project. Include all extractable fields."},
    {"name": "search_projects", "description": "Semantic search by name/description. Always search before creating."},
    {"name": "list_projects", "description": "List all projects. Supports pagination and filters (project_type, status, tags)."},
    {"name": "get_project", "description": "Fetch full details by ID."},
    {"name": "update_project", "description": "Modify project fields."},
    {"name": "delete_project", "description": "Remove a project (only if user explicitly asks)."},
]


def get_project_prompt(user_name: str | None = None, tools: list | None = None) -> str:
    """Render the project agent system prompt with context variables."""
    return render_prompt(
        "project_agent",
        user_name=user_name,
        tools=tools or DEFAULT_TOOLS,
        project_types=PROJECT_TYPES,
        project_statuses=PROJECT_STATUSES,
    )


# Backwards-compatible constant
PROJECT_AGENT_PROMPT = get_project_prompt()
