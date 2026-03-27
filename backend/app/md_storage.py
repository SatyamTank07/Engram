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
# Collection + Tree generation (PageIndex integration)
# ---------------------------------------------------------------------------
_TYPE_TITLES: dict[str, str] = {
    "idea": "Ideas",
    "content": "Content",
    "project": "Projects",
}


async def _rebuild_collection(user_id: str, entity_type: str) -> Path:
    """Regenerate ``_collection.md`` from all entity .md files.

    The collection file is a single Markdown document with ``## Entity Name``
    sections — suitable for PageIndex tree generation.
    """
    entity_dir = _get_entity_dir(user_id, entity_type)
    index = _load_index(user_id, entity_type)
    display_field = _DISPLAY_FIELD.get(entity_type, "name")
    type_title = _TYPE_TITLES.get(entity_type, entity_type.title())

    lines: list[str] = [f"# {type_title}\n"]
    for entity_id, entry in index.items():
        entity = await get_entity(user_id, entity_type, entity_id)
        if not entity:
            continue
        display_name = entity.get(display_field, "untitled")
        lines.append(f"\n## {display_name} ({entity_id[:8]})")
        # Metadata line
        subtype = entity.get(_SUBTYPE_FIELD.get(entity_type, ""), "")
        status = entity.get("status", "")
        tags = ", ".join(entity.get("tags", []))
        meta_line = f"- **Type:** {subtype} | **Status:** {status} | **Tags:** {tags}"
        if entity_type == "idea" and entity.get("confidence"):
            meta_line += f" | **Confidence:** {entity['confidence']}"
        elif entity_type == "content" and entity.get("your_rating"):
            meta_line += f" | **Rating:** {entity['your_rating']}"
        elif entity_type == "project" and entity.get("priority"):
            meta_line += f" | **Priority:** {entity['priority']}"
        lines.append(meta_line)
        # Body sections
        for bf in _BODY_FIELDS.get(entity_type, []):
            val = entity.get(bf, "")
            if val:
                heading = bf.replace("_", " ").title()
                lines.append(f"\n### {heading}\n{val}")

    collection_path = entity_dir / "_collection.md"
    collection_path.write_text("\n".join(lines), encoding="utf-8")
    return collection_path


async def _rebuild_tree(user_id: str, entity_type: str) -> None:
    """Rebuild PageIndex tree from ``_collection.md``.

    Falls back to a simple hierarchical grouping (status -> subtype -> entities)
    when PageIndex or the required LLM is unavailable.
    """
    entity_dir = _get_entity_dir(user_id, entity_type)
    collection_path = entity_dir / "_collection.md"
    if not collection_path.exists():
        return

    # Try PageIndex first
    try:
        from pageindex.page_index_md import md_to_tree  # type: ignore[import-untyped]

        tree = await md_to_tree(
            md_path=str(collection_path),
            model=os.environ.get("PAGEINDEX_MODEL", "gpt-4o-2024-11-20"),
            if_add_node_summary="yes",
            if_add_node_id="yes",
            if_add_node_text="no",
        )
        tree_path = entity_dir / "_tree.json"
        tree_path.write_text(
            json.dumps(tree, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("PageIndex tree generated for %s/%s", user_id, entity_type)
        return
    except Exception as exc:
        logger.info(
            "PageIndex tree generation unavailable for %s/%s, using fallback: %s",
            user_id,
            entity_type,
            exc,
        )

    # Fallback: build a simple hierarchical tree from the index
    tree = _build_fallback_tree(user_id, entity_type)
    tree_path = entity_dir / "_tree.json"
    tree_path.write_text(
        json.dumps(tree, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.debug("Fallback tree generated for %s/%s", user_id, entity_type)


def _build_fallback_tree(user_id: str, entity_type: str) -> dict:
    """Build a hierarchical tree grouped by status -> subtype -> entities.

    Returns a dict with the same top-level shape as PageIndex output so that
    downstream consumers can treat them uniformly.
    """
    index = _load_index(user_id, entity_type)
    display_field = _DISPLAY_FIELD.get(entity_type, "name")
    subtype_field = _SUBTYPE_FIELD.get(entity_type, "")

    # Group: status -> subtype -> list of entity summaries
    groups: dict[str, dict[str, list[dict]]] = {}
    for entity_id, entry in index.items():
        status = entry.get("status", "unknown")
        subtype = entry.get(subtype_field, "general") if subtype_field else "general"
        groups.setdefault(status, {}).setdefault(subtype, []).append(
            {
                "entity_id": entity_id,
                "title": entry.get(display_field, "untitled"),
                "tags": entry.get("tags", []),
            }
        )

    # Convert to tree structure
    type_title = _TYPE_TITLES.get(entity_type, entity_type.title())
    structure: list[dict] = []
    for status, subtypes in sorted(groups.items()):
        status_node: dict[str, Any] = {
            "title": f"Status: {status}",
            "children": [],
        }
        for subtype, entities in sorted(subtypes.items()):
            subtype_node: dict[str, Any] = {
                "title": f"Type: {subtype}",
                "children": [
                    {
                        "title": f"{e['title']} ({e['entity_id'][:8]})",
                        "entity_id": e["entity_id"],
                        "tags": e["tags"],
                    }
                    for e in entities
                ],
            }
            status_node["children"].append(subtype_node)
        structure.append(status_node)

    return {
        "doc_name": f"{user_id}-{entity_type}",
        "doc_description": f"Hierarchical index of {type_title} for user {user_id}",
        "structure": structure,
    }


_rebuild_timers: dict[tuple[str, str], asyncio.Task] = {}  # type: ignore[type-arg]


async def _rebuild_collection_and_tree(user_id: str, entity_type: str) -> None:
    """Debounced rebuild — waits 2 s to batch rapid CRUD ops, then rebuilds."""
    key = (user_id, entity_type)
    # Cancel any pending rebuild for this (user, type)
    if key in _rebuild_timers and not _rebuild_timers[key].done():
        _rebuild_timers[key].cancel()

    async def _do_rebuild() -> None:
        await asyncio.sleep(2)  # debounce delay
        await _rebuild_collection(user_id, entity_type)
        await _rebuild_tree(user_id, entity_type)

    _rebuild_timers[key] = asyncio.create_task(_do_rebuild())


# ---------------------------------------------------------------------------
# Tree loading
# ---------------------------------------------------------------------------
def _load_tree(user_id: str, entity_type: str) -> dict | None:
    """Load the PageIndex tree from ``_tree.json``. Returns *None* when absent."""
    tree_path = _get_entity_dir(user_id, entity_type) / "_tree.json"
    if not tree_path.exists():
        return None
    try:
        return json.loads(tree_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load tree for %s/%s: %s", user_id, entity_type, exc)
        return None


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
async def search_entities(
    user_id: str,
    entity_type: str,
    query: str,
    limit: int = 20,
) -> list[dict]:
    """Search entities using keyword scoring against the index.

    Scores each entity by matching *query* terms against the display field,
    tags, status, and subtype.  Returns the top *limit* results as full
    entity dicts, sorted by descending relevance score.
    """
    index = _load_index(user_id, entity_type)
    if not index:
        return []

    display_field = _DISPLAY_FIELD.get(entity_type, "name")
    subtype_field = _SUBTYPE_FIELD.get(entity_type, "")
    query_terms = [t for t in query.lower().split() if t]
    if not query_terms:
        return []

    scored: list[tuple[float, str]] = []
    for entity_id, entry in index.items():
        score = 0.0
        # Display field (highest weight)
        display_val = entry.get(display_field, "").lower()
        for term in query_terms:
            if term in display_val:
                score += 3.0
        # Tags
        tag_str = " ".join(entry.get("tags", [])).lower()
        for term in query_terms:
            if term in tag_str:
                score += 2.0
        # Status
        status_val = entry.get("status", "").lower()
        for term in query_terms:
            if term in status_val:
                score += 1.0
        # Subtype
        if subtype_field:
            subtype_val = entry.get(subtype_field, "").lower()
            for term in query_terms:
                if term in subtype_val:
                    score += 1.5
        if score > 0:
            scored.append((score, entity_id))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    results: list[dict] = []
    for _score, eid in scored[:limit]:
        entity = await get_entity(user_id, entity_type, eid)
        if entity:
            results.append(entity)
    return results


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
