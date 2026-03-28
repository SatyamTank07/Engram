"""
Jinja2-based prompt loader for agent system prompts.

Loads .j2 templates from each agent's templates/ directory and renders
them with the provided context variables.
"""

from pathlib import Path
from functools import lru_cache

from jinja2 import Environment, FileSystemLoader, select_autoescape

# Root directory for all agent templates
_AGENTS_DIR = Path(__file__).parent.parent


@lru_cache(maxsize=None)
def _get_env(agent_name: str) -> Environment:
    """Return a cached Jinja2 Environment for the given agent's templates/ dir."""
    template_dir = _AGENTS_DIR / agent_name / "templates"
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape([]),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=False,
    )


def render_prompt(agent_name: str, template_file: str = "system_prompt.j2", **kwargs) -> str:
    """Render a Jinja2 template for the given agent.

    Args:
        agent_name: Agent directory name (e.g. "person_agent", "orchestrator").
        template_file: Template filename inside the agent's templates/ dir.
        **kwargs: Variables passed into the template context.

    Returns:
        The rendered prompt string.
    """
    env = _get_env(agent_name)
    template = env.get_template(template_file)
    return template.render(**kwargs)
