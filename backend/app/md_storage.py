"""
Markdown file storage — helpers and CRUD for idea/content/project entities.

Each entity is stored as a YAML-frontmatter `.md` file under:
    DATA_DIR/{user_id}/{entity_type_plural}/

An `_index.json` per (user_id, entity_type) provides fast lookup without
scanning the filesystem.

All write operations (file + index) are serialized per (user_id, entity_type)
via an asyncio.Lock to prevent concurrent corruption.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import re
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import frontmatter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DATA_DIR = os.environ.get(
    "DATA_DIR",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data",
    ),
)

_DIR_NAMES: dict[str, str] = {
    "idea": "ideas",
    "content": "content",
    "project": "projects",
}

_DISPLAY_FIELD: dict[str, str] = {
    "idea": "name",
    "content": "title",
    "project": "name",
}

_SUBTYPE_FIELD: dict[str, str] = {
    "idea": "idea_type",
    "content": "content_type",
    "project": "project_type",
}

_BODY_FIELDS: dict[str, list[str]] = {
    "idea": ["description", "notes"],
    "content": ["personal_notes"],
    "project": ["description", "notes"],
}

_INDEX_FIELDS: dict[str, list[str]] = {
    "idea": ["name", "idea_type", "status", "tags"],
    "content": ["title", "content_type", "status", "tags"],
    "project": ["name", "project_type", "status", "tags"],
}

_DEFAULTS: dict[str, dict[str, Any]] = {
    "idea": {"status": "active"},
    "content": {"status": "want"},
    "project": {"status": "planned"},
}

# ---------------------------------------------------------------------------
# Per-(user_id, entity_type) locks for concurrency safety
# ---------------------------------------------------------------------------
_index_locks: dict[tuple[str, str], asyncio.Lock] = {}


def _get_lock(user_id: str, entity_type: str) -> asyncio.Lock:
    """Return (and lazily create) an asyncio.Lock for the given scope."""
    key = (user_id, entity_type)
    return _index_locks.setdefault(key, asyncio.Lock())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _slugify(text: str) -> str:
    """Lowercase, replace non-alphanumeric with hyphens, collapse runs, max 50 chars."""
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    if not s:
        return "untitled"
    return s[:50]


def _build_filename(display_name: str, entity_id: str, date: str) -> str:
    """Build `YYYY-MM-DD-slug-shortid.md`."""
    slug = _slugify(display_name)
    short_id = entity_id.split("-")[0]  # first 8 hex chars
    return f"{date}-{slug}-{short_id}.md"


def _get_entity_dir(user_id: str, entity_type: str) -> Path:
    """Return the directory path for the given user + entity type, creating it if needed."""
    p = Path(DATA_DIR) / user_id / _DIR_NAMES[entity_type]
    os.makedirs(p, exist_ok=True)
    return p


_IS_WINDOWS = platform.system() == "Windows"


def _atomic_replace(src: str, dst: str, retries: int = 3, delay: float = 0.05) -> None:
    """os.replace with retry logic for Windows (file-locking edge cases)."""
    for attempt in range(retries):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if not _IS_WINDOWS or attempt == retries - 1:
                raise
            time.sleep(delay * (attempt + 1))


def _write_md_file(filepath: Path | str, frontmatter_dict: dict, body: str) -> None:
    """Atomically write a markdown file with YAML frontmatter + body."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    post = frontmatter.Post(body, **frontmatter_dict)
    content = frontmatter.dumps(post)

    # Atomic: write to temp file in same directory, then os.replace()
    fd, tmp_path = tempfile.mkstemp(dir=str(filepath.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        _atomic_replace(tmp_path, str(filepath))
    except BaseException:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _parse_md_file(filepath: Path | str) -> dict:
    """Parse a markdown file and return frontmatter fields + `_body`."""
    filepath = Path(filepath)
    text = filepath.read_text(encoding="utf-8")
    post = frontmatter.loads(text)
    result = dict(post.metadata)
    result["_body"] = post.content
    return result


def _load_index(user_id: str, entity_type: str) -> dict:
    """Load `_index.json` for the given scope. Returns {} if missing."""
    index_path = _get_entity_dir(user_id, entity_type) / "_index.json"
    if not index_path.exists():
        return {}
    text = index_path.read_text(encoding="utf-8")
    return json.loads(text)


def _save_index(user_id: str, entity_type: str, index: dict) -> None:
    """Atomically write `_index.json`."""
    entity_dir = _get_entity_dir(user_id, entity_type)
    entity_dir.mkdir(parents=True, exist_ok=True)
    index_path = entity_dir / "_index.json"

    content = json.dumps(index, indent=2, ensure_ascii=False)
    fd, tmp_path = tempfile.mkstemp(dir=str(entity_dir), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        _atomic_replace(tmp_path, str(index_path))
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _split_body(entity_type: str, data: dict) -> tuple[dict, str]:
    """Separate body fields from data.

    Returns (frontmatter_dict, body_str). Body fields are rendered as
    ``## Field Name`` markdown sections.
    """
    body_field_names = _BODY_FIELDS.get(entity_type, [])
    fm = {k: v for k, v in data.items() if k not in body_field_names}
    sections: list[str] = []
    for field in body_field_names:
        value = data.get(field, "")
        if value:
            # Convert field_name to Title Case heading
            heading = field.replace("_", " ").title()
            sections.append(f"## {heading}\n{value}")
    body = "\n\n".join(sections)
    return fm, body


def _merge_body_into_dict(entity_type: str, parsed: dict) -> dict:
    """Merge ``_body`` markdown sections back into a flat dict."""
    result = {k: v for k, v in parsed.items() if k != "_body"}
    raw_body = parsed.get("_body", "")
    body_field_names = _BODY_FIELDS.get(entity_type, [])

    # Parse sections: split on ## headings
    # Build a mapping from heading (lowered, underscored) -> content
    section_map: dict[str, str] = {}
    if raw_body.strip():
        # Split into sections by ## headings
        parts = re.split(r"^## (.+)$", raw_body, flags=re.MULTILINE)
        # parts: ['', 'Description', '\ncontent...', 'Notes', '\ncontent...', ...]
        # Index 0 is text before the first heading (usually empty)
        i = 1
        while i < len(parts) - 1:
            heading = parts[i].strip()
            content = parts[i + 1].strip()
            key = heading.lower().replace(" ", "_")
            section_map[key] = content
            i += 2

    for field in body_field_names:
        result[field] = section_map.get(field, "")

    return result


def _build_index_entry(entity_type: str, data: dict, filename: str) -> dict:
    """Build an index entry dict from entity data."""
    entry: dict[str, Any] = {"filename": filename}
    for field in _INDEX_FIELDS[entity_type]:
        if field in data:
            entry[field] = data[field]
    # Always include timestamps
    if "first_seen" in data:
        entry["first_seen"] = data["first_seen"]
    if "last_seen" in data:
        entry["last_seen"] = data["last_seen"]
    return entry


# ---------------------------------------------------------------------------
# Stub for tree rebuild (Task 3 will implement the real version)
# ---------------------------------------------------------------------------
async def _rebuild_collection_and_tree(user_id: str, entity_type: str) -> None:
    """Stub — Task 3 will replace this with PageIndex tree generation."""
    logger.debug("_rebuild_collection_and_tree called for %s/%s (stub)", user_id, entity_type)


# ---------------------------------------------------------------------------
# CRUD (all async)
# ---------------------------------------------------------------------------
async def create_entity(
    user_id: str,
    entity_type: str,
    data: dict,
) -> dict:
    """Create a new entity. Returns the full entity dict."""
    entity_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Apply defaults
    merged = dict(_DEFAULTS.get(entity_type, {}))
    merged.update(data)
    merged["id"] = entity_id
    merged["type"] = entity_type
    merged["user_id"] = user_id
    merged["first_seen"] = now
    merged["last_seen"] = now
    merged.setdefault("tags", [])
    merged.setdefault("relationships", [])
    merged.setdefault("confidence", None)

    # Determine display name and date for filename
    display_field = _DISPLAY_FIELD[entity_type]
    display_name = merged.get(display_field, "untitled")
    date_str = now[:10]  # YYYY-MM-DD from ISO string

    filename = _build_filename(display_name, entity_id, date_str)

    # Split body fields from frontmatter
    fm, body = _split_body(entity_type, merged)

    entity_dir = _get_entity_dir(user_id, entity_type)

    async with _get_lock(user_id, entity_type):
        _write_md_file(entity_dir / filename, fm, body)

        # Update index
        index = _load_index(user_id, entity_type)
        index[entity_id] = _build_index_entry(entity_type, merged, filename)
        _save_index(user_id, entity_type, index)

    # Trigger background rebuild (fire and forget)
    asyncio.create_task(_rebuild_collection_and_tree(user_id, entity_type))

    # Return the full entity dict (with body fields)
    return merged


async def get_entity(
    user_id: str,
    entity_type: str,
    entity_id: str,
) -> dict | None:
    """Fetch a single entity by ID. Returns None if not found."""
    index = _load_index(user_id, entity_type)
    entry = index.get(entity_id)
    if entry is None:
        return None

    filepath = _get_entity_dir(user_id, entity_type) / entry["filename"]
    if not filepath.exists():
        return None

    parsed = _parse_md_file(filepath)
    return _merge_body_into_dict(entity_type, parsed)


async def list_entities(
    user_id: str,
    entity_type: str,
    limit: int = 50,
    offset: int = 0,
    **filters: Any,
) -> tuple[list[dict], int]:
    """List entities with optional filtering and pagination.

    Supported filters: ``status``, ``tags`` (list — match any),
    and the entity-specific subtype field (e.g. ``idea_type``).

    Returns (items, total_before_pagination).
    """
    index = _load_index(user_id, entity_type)

    # Determine which filters apply
    status_filter = filters.get("status")
    tags_filter = filters.get("tags")  # list of tags, match any
    subtype_field = _SUBTYPE_FIELD.get(entity_type)
    subtype_filter = filters.get(subtype_field) if subtype_field else None

    # Filter index entries
    matching_ids: list[str] = []
    for eid, entry in index.items():
        if status_filter and entry.get("status") != status_filter:
            continue
        if tags_filter:
            entry_tags = set(entry.get("tags", []))
            if not entry_tags.intersection(tags_filter):
                continue
        if subtype_filter and subtype_field:
            if entry.get(subtype_field) != subtype_filter:
                continue
        matching_ids.append(eid)

    total = len(matching_ids)

    # Paginate
    page_ids = matching_ids[offset : offset + limit]

    # Read full entity dicts for the page
    items: list[dict] = []
    entity_dir = _get_entity_dir(user_id, entity_type)
    for eid in page_ids:
        entry = index[eid]
        filepath = entity_dir / entry["filename"]
        if filepath.exists():
            parsed = _parse_md_file(filepath)
            items.append(_merge_body_into_dict(entity_type, parsed))

    return items, total


async def update_entity(
    user_id: str,
    entity_type: str,
    entity_id: str,
    updates: dict,
) -> dict | None:
    """Update an existing entity. Returns the updated dict, or None if not found."""
    async with _get_lock(user_id, entity_type):
        index = _load_index(user_id, entity_type)
        entry = index.get(entity_id)
        if entry is None:
            return None

        filepath = _get_entity_dir(user_id, entity_type) / entry["filename"]
        if not filepath.exists():
            return None

        # Read current state
        parsed = _parse_md_file(filepath)
        current = _merge_body_into_dict(entity_type, parsed)

        # Merge updates
        current.update(updates)

        # Refresh last_seen
        current["last_seen"] = datetime.now(timezone.utc).isoformat()

        # Split and rewrite
        fm, body = _split_body(entity_type, current)
        _write_md_file(filepath, fm, body)

        # Update index entry
        index[entity_id] = _build_index_entry(entity_type, current, entry["filename"])
        _save_index(user_id, entity_type, index)

    # Trigger background rebuild
    asyncio.create_task(_rebuild_collection_and_tree(user_id, entity_type))

    return current


async def delete_entity(
    user_id: str,
    entity_type: str,
    entity_id: str,
) -> bool:
    """Delete an entity. Returns True if deleted, False if not found."""
    async with _get_lock(user_id, entity_type):
        index = _load_index(user_id, entity_type)
        entry = index.get(entity_id)
        if entry is None:
            return False

        filepath = _get_entity_dir(user_id, entity_type) / entry["filename"]
        if filepath.exists():
            filepath.unlink()

        del index[entity_id]
        _save_index(user_id, entity_type, index)

    # Trigger background rebuild
    asyncio.create_task(_rebuild_collection_and_tree(user_id, entity_type))

    return True


async def rebuild_index(user_id: str, entity_type: str) -> dict:
    """Scan entity dir for all .md files, rebuild index from scratch, and save it."""
    entity_dir = _get_entity_dir(user_id, entity_type)
    new_index: dict[str, dict] = {}

    for filepath in sorted(entity_dir.glob("*.md")):
        try:
            parsed = _parse_md_file(filepath)
            merged = _merge_body_into_dict(entity_type, parsed)
            entity_id = merged.get("id")
            if entity_id:
                entry = _build_index_entry(entity_type, merged, filepath.name)
                new_index[entity_id] = entry
        except Exception:
            logger.warning("Skipping unparseable file: %s", filepath, exc_info=True)

    _save_index(user_id, entity_type, new_index)
    return new_index
