"""
A2A protocol utility helpers shared across all sub-agents.
"""

import json
import logging

logger = logging.getLogger(__name__)


def extract_user_id(task) -> str | None:
    """Extract user_id from A2A task message metadata.

    The orchestrator (or direct caller) passes user_id in the message
    metadata so that tools can be scoped to the authenticated user.
    """
    try:
        message = task.message or {}
        metadata = message.get("metadata", {})
        return metadata.get("user_id")
    except Exception:
        return None


def extract_message_text(task) -> str:
    """Extract the text content from an A2A task message."""
    try:
        message = task.message or {}
        content = message.get("content", {})
        if isinstance(content, dict):
            return content.get("text", "")
        if isinstance(content, str):
            return content
        return ""
    except Exception:
        return ""


def build_completed_task(task, response_text: str):
    """Mark an A2A task as completed with a text response artifact."""
    from python_a2a import TaskStatus, TaskState

    task.artifacts = [{"parts": [{"type": "text", "text": response_text}]}]
    task.status = TaskStatus(state=TaskState.COMPLETED)
    return task


def build_failed_task(task, error_msg: str):
    """Mark an A2A task as failed with an error message."""
    from python_a2a import TaskStatus, TaskState

    task.artifacts = [{"parts": [{"type": "text", "text": f"Error: {error_msg}"}]}]
    task.status = TaskStatus(state=TaskState.FAILED)
    return task
