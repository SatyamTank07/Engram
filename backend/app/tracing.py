"""
Request-scoped agent/tool call tracing.

Uses contextvars to carry a trace object through the async call chain
(agent -> orchestrator -> sub-agent -> tool) without modifying function signatures.

Toggle via AGENT_TRACING_ENABLED env var.
"""

import json
import os
import time
import uuid
import logging
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

AGENT_TRACING_ENABLED = os.getenv("AGENT_TRACING_ENABLED", "true").lower() in ("true", "1", "yes")
MAX_TRACE_RESULT_LENGTH = 2000


def _safe_serialize(value: Any) -> Any:
    """Serialize a value to a JSON-safe type, truncating if needed."""
    try:
        s = json.dumps(value, default=str)
    except (TypeError, ValueError):
        s = str(value)
    if len(s) > MAX_TRACE_RESULT_LENGTH:
        return s[:MAX_TRACE_RESULT_LENGTH] + "... [truncated]"
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return s


@dataclass
class ToolCallEntry:
    tool_name: str
    args: dict
    result: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "args": _safe_serialize(self.args),
            "result": _safe_serialize(self.result),
            "error": self.error,
            "duration_ms": round(self.duration_ms, 2),
        }


@dataclass
class AgentSpan:
    agent_name: str
    tool_calls: list[ToolCallEntry] = field(default_factory=list)
    child_spans: list["AgentSpan"] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    duration_ms: float = 0.0
    _parent: Optional["AgentSpan"] = field(default=None, repr=False)

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "child_spans": [cs.to_dict() for cs in self.child_spans],
            "duration_ms": round(self.duration_ms, 2),
        }


@dataclass
class RequestTrace:
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_spans: list[AgentSpan] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    duration_ms: float = 0.0

    def finalize(self):
        self.duration_ms = (time.time() - self.started_at) * 1000

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "duration_ms": round(self.duration_ms, 2),
            "agent_spans": [s.to_dict() for s in self.agent_spans],
        }


# ---------------------------------------------------------------------------
# Context variables
# ---------------------------------------------------------------------------
_current_trace: ContextVar[Optional[RequestTrace]] = ContextVar("_current_trace", default=None)
_current_agent_span: ContextVar[Optional[AgentSpan]] = ContextVar("_current_agent_span", default=None)


def start_trace() -> Optional[RequestTrace]:
    """Start a new request trace. Returns None if tracing is disabled."""
    if not AGENT_TRACING_ENABLED:
        return None
    trace = RequestTrace()
    _current_trace.set(trace)
    _current_agent_span.set(None)
    return trace


def get_trace() -> Optional[RequestTrace]:
    return _current_trace.get()


def start_agent_span(agent_name: str) -> Optional[AgentSpan]:
    """Start a new agent span. Nests under the current span if one exists."""
    if not AGENT_TRACING_ENABLED:
        return None
    trace = _current_trace.get()
    if not trace:
        return None

    parent_span = _current_agent_span.get()
    span = AgentSpan(agent_name=agent_name, _parent=parent_span)
    if parent_span:
        parent_span.child_spans.append(span)
    else:
        trace.agent_spans.append(span)
    _current_agent_span.set(span)
    return span


def end_agent_span():
    """Finalize the current agent span and restore the parent span."""
    if not AGENT_TRACING_ENABLED:
        return
    span = _current_agent_span.get()
    if not span:
        _current_agent_span.set(None)
        return

    span.duration_ms = (time.time() - span.started_at) * 1000
    _current_agent_span.set(span._parent)


def log_tool_call(tool_name: str, args: dict, result: Any = None, error: str = None, duration_ms: float = 0.0):
    """Record a tool call in the current agent span."""
    if not AGENT_TRACING_ENABLED:
        return
    span = _current_agent_span.get()
    if not span:
        return
    entry = ToolCallEntry(
        tool_name=tool_name,
        args=args,
        result=result,
        error=error,
        duration_ms=duration_ms,
    )
    span.tool_calls.append(entry)


def finalize_trace() -> Optional[dict]:
    """Finalize the current trace and return its dict representation."""
    trace = _current_trace.get()
    if not trace:
        return None
    trace.finalize()
    result = trace.to_dict()
    # Clean up context
    _current_trace.set(None)
    _current_agent_span.set(None)
    return result
