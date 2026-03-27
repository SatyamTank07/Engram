"""Tests for md_storage module — helpers, CRUD, index management."""

import asyncio
import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Set DATA_DIR to a temp directory BEFORE importing md_storage
_TEST_DATA_DIR = tempfile.mkdtemp()
os.environ["DATA_DIR"] = _TEST_DATA_DIR

from app import md_storage
from app.md_storage import (
    _slugify, _build_filename, _get_entity_dir,
    _write_md_file, _parse_md_file,
    _load_index, _save_index,
    _split_body, _merge_body_into_dict,
    _load_tree,
    _rebuild_collection, _rebuild_tree, _build_fallback_tree,
    create_entity, get_entity, list_entities, update_entity, delete_entity,
    rebuild_index, search_entities,
    DATA_DIR,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _clean_data_dir():
    """Reset DATA_DIR contents and index locks before each test."""
    import shutil

    # Clear any leftover data
    for item in Path(_TEST_DATA_DIR).iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    # Clear cached locks so tests don't share state
    md_storage._index_locks.clear()
    yield


@pytest.fixture
def user_id():
    return "test-user-123"


@pytest.fixture
def sample_idea_data():
    return {
        "name": "My Startup Idea",
        "idea_type": "hypothesis",
        "status": "active",
        "confidence": 0.7,
        "tags": ["startup", "ai"],
        "description": "A platform that uses AI to automate things.",
        "notes": "Early stage thinking.",
    }


@pytest.fixture
def sample_content_data():
    return {
        "title": "Great Blog Post",
        "content_type": "article",
        "status": "consumed",
        "tags": ["tech", "reading"],
        "personal_notes": "Really insightful article about ML.",
    }


@pytest.fixture
def sample_project_data():
    return {
        "name": "Side Project Alpha",
        "project_type": "personal",
        "status": "in_progress",
        "tags": ["code", "python"],
        "description": "Building a CLI tool for X.",
        "notes": "Started last week.",
    }


# ---------------------------------------------------------------------------
# _slugify tests
# ---------------------------------------------------------------------------
class TestSlugify:
    def test_basic(self):
        assert md_storage._slugify("Hello World") == "hello-world"

    def test_special_chars(self):
        assert md_storage._slugify("foo@bar!baz") == "foo-bar-baz"
        assert md_storage._slugify("Hello, World! @2024") == "hello-world-2024"

    def test_multiple_spaces_and_hyphens(self):
        result = md_storage._slugify("  too   many---spaces  ")
        assert "--" not in result
        assert result == "too-many-spaces"

    def test_truncation(self):
        long_text = "a" * 100
        result = md_storage._slugify(long_text)
        assert len(result) <= 50

    def test_unicode(self):
        result = md_storage._slugify("Cafe Resume")
        assert result == "cafe-resume"

    def test_empty_string(self):
        result = md_storage._slugify("")
        assert result == "untitled"

    def test_only_special_chars(self):
        result = md_storage._slugify("@#$%^&*()")
        assert result == "untitled"

    def test_preserves_numbers(self):
        result = md_storage._slugify("Version 2.0 Release")
        assert "version" in result
        assert "20" in result or "2" in result


# ---------------------------------------------------------------------------
# _build_filename tests
# ---------------------------------------------------------------------------
class TestBuildFilename:
    def test_format(self):
        result = md_storage._build_filename("My Idea", "a3f7b2c1-4d5e-6f7a-8b9c-0d1e2f3a4b5c", "2024-03-15")
        assert result.startswith("2024-03-15-")
        assert result.endswith(".md")
        assert "a3f7b2c1" in result  # short UUID prefix

    def test_slug_in_filename(self):
        result = md_storage._build_filename("My Cool Idea", "a3f7b2c1-xxxx", "2024-01-01")
        assert "my-cool-idea" in result

    def test_short_uuid_prefix(self):
        eid = "abcdef01-2345-6789-0000-111111111111"
        result = md_storage._build_filename("Test", eid, "2024-06-01")
        assert "abcdef01" in result

    def test_full_format(self):
        result = md_storage._build_filename("Test Name", "12345678-abcd-efgh-ijkl-mnopqrstuvwx", "2024-06-15")
        assert result == "2024-06-15-test-name-12345678.md"


# ---------------------------------------------------------------------------
# _write_md_file / _parse_md_file roundtrip tests
# ---------------------------------------------------------------------------
class TestWriteParseRoundtrip:
    def test_roundtrip(self, tmp_path):
        filepath = tmp_path / "test.md"
        fm = {
            "id": "abc-123",
            "type": "idea",
            "name": "Test Idea",
            "tags": ["a", "b"],
        }
        body = "## Description\nSome description.\n\n## Notes\nSome notes."

        md_storage._write_md_file(filepath, fm, body)
        parsed = md_storage._parse_md_file(filepath)

        assert parsed["id"] == "abc-123"
        assert parsed["type"] == "idea"
        assert parsed["name"] == "Test Idea"
        assert parsed["tags"] == ["a", "b"]
        assert "Some description." in parsed.get("_body", "")

    def test_empty_body(self, tmp_path):
        filepath = tmp_path / "empty_body.md"
        fm = {"id": "xyz", "type": "content"}
        md_storage._write_md_file(filepath, fm, "")
        parsed = md_storage._parse_md_file(filepath)
        assert parsed["id"] == "xyz"

    def test_utf8_content(self, tmp_path):
        filepath = tmp_path / "utf8.md"
        fm = {"id": "u8", "name": "Test UTF8"}
        md_storage._write_md_file(filepath, fm, "## Notes\nSpecial chars: arrows and dashes.")
        parsed = md_storage._parse_md_file(filepath)
        assert parsed["name"] == "Test UTF8"
        assert "Special chars" in parsed.get("_body", "")

    def test_file_created_with_utf8_encoding(self, tmp_path):
        filepath = tmp_path / "encoding.md"
        md_storage._write_md_file(filepath, {"id": "enc"}, "body text")
        content = filepath.read_text(encoding="utf-8")
        assert "id: enc" in content
        assert "body text" in content

    def test_creates_parent_dirs(self, tmp_path):
        filepath = tmp_path / "deep" / "nested" / "dir" / "test.md"
        md_storage._write_md_file(filepath, {"id": "nested"}, "body")
        assert filepath.exists()


# ---------------------------------------------------------------------------
# _load_index / _save_index tests
# ---------------------------------------------------------------------------
class TestIndexIO:
    def test_load_missing_returns_empty(self, user_id):
        result = md_storage._load_index(user_id, "idea")
        assert result == {}

    def test_save_and_load_roundtrip(self, user_id):
        index = {
            "id-1": {
                "filename": "2024-01-01-test-id1.md",
                "name": "Test",
                "status": "active",
                "tags": ["a"],
            }
        }
        # Ensure directory exists
        entity_dir = md_storage._get_entity_dir(user_id, "idea")
        entity_dir.mkdir(parents=True, exist_ok=True)

        md_storage._save_index(user_id, "idea", index)
        loaded = md_storage._load_index(user_id, "idea")
        assert loaded == index

    def test_save_overwrites(self, user_id):
        entity_dir = md_storage._get_entity_dir(user_id, "idea")
        entity_dir.mkdir(parents=True, exist_ok=True)

        md_storage._save_index(user_id, "idea", {"a": {"name": "First"}})
        md_storage._save_index(user_id, "idea", {"b": {"name": "Second"}})
        loaded = md_storage._load_index(user_id, "idea")
        assert "b" in loaded
        assert "a" not in loaded

    def test_save_creates_directory(self, user_id):
        """_save_index creates the entity directory if it does not exist."""
        index = {"x": {"filename": "test.md"}}
        md_storage._save_index(user_id, "idea", index)
        loaded = md_storage._load_index(user_id, "idea")
        assert loaded == index


# ---------------------------------------------------------------------------
# _get_entity_dir tests
# ---------------------------------------------------------------------------
class TestGetEntityDir:
    def test_idea_dir(self, user_id):
        p = md_storage._get_entity_dir(user_id, "idea")
        assert p == Path(_TEST_DATA_DIR) / user_id / "ideas"

    def test_content_dir(self, user_id):
        p = md_storage._get_entity_dir(user_id, "content")
        assert p == Path(_TEST_DATA_DIR) / user_id / "content"

    def test_project_dir(self, user_id):
        p = md_storage._get_entity_dir(user_id, "project")
        assert p == Path(_TEST_DATA_DIR) / user_id / "projects"


# ---------------------------------------------------------------------------
# _split_body / _merge_body_into_dict tests
# ---------------------------------------------------------------------------
class TestSplitAndMergeBody:
    def test_split_body_idea(self):
        data = {
            "name": "Test",
            "description": "Desc text",
            "notes": "Notes text",
            "status": "active",
        }
        fm, body = md_storage._split_body("idea", data)
        assert "description" not in fm
        assert "notes" not in fm
        assert fm["name"] == "Test"
        assert "## Description" in body
        assert "Desc text" in body
        assert "## Notes" in body
        assert "Notes text" in body

    def test_split_body_content(self):
        data = {
            "title": "Blog",
            "personal_notes": "My thoughts",
            "status": "consumed",
        }
        fm, body = md_storage._split_body("content", data)
        assert "personal_notes" not in fm
        assert "## Personal Notes" in body

    def test_merge_body_into_dict_idea(self):
        parsed = {
            "id": "abc",
            "name": "Test",
            "status": "active",
            "_body": "## Description\nDesc text\n\n## Notes\nNotes text",
        }
        result = md_storage._merge_body_into_dict("idea", parsed)
        assert result["description"] == "Desc text"
        assert result["notes"] == "Notes text"
        assert "_body" not in result

    def test_merge_body_empty_sections(self):
        parsed = {
            "id": "abc",
            "_body": "",
        }
        result = md_storage._merge_body_into_dict("idea", parsed)
        assert result.get("description", "") == ""
        assert result.get("notes", "") == ""

    def test_split_and_merge_roundtrip(self):
        """Split body fields out, then merge them back and verify equality."""
        data = {
            "name": "Roundtrip",
            "status": "active",
            "description": "Some description",
            "notes": "Some notes",
        }
        fm, body = md_storage._split_body("idea", data)
        # Simulate what _parse_md_file returns
        parsed = dict(fm)
        parsed["_body"] = body
        result = md_storage._merge_body_into_dict("idea", parsed)
        assert result["description"] == "Some description"
        assert result["notes"] == "Some notes"
        assert result["name"] == "Roundtrip"


# ---------------------------------------------------------------------------
# _build_index_entry tests
# ---------------------------------------------------------------------------
class TestBuildIndexEntry:
    def test_includes_index_fields(self):
        data = {
            "name": "Test Idea",
            "idea_type": "hypothesis",
            "status": "active",
            "tags": ["ai"],
            "first_seen": "2024-01-01T00:00:00Z",
            "last_seen": "2024-01-01T00:00:00Z",
            "description": "Should not appear in index entry",
        }
        entry = md_storage._build_index_entry("idea", data, "test.md")
        assert entry["filename"] == "test.md"
        assert entry["name"] == "Test Idea"
        assert entry["idea_type"] == "hypothesis"
        assert entry["status"] == "active"
        assert entry["tags"] == ["ai"]
        assert entry["first_seen"] == "2024-01-01T00:00:00Z"
        assert entry["last_seen"] == "2024-01-01T00:00:00Z"
        # body fields should NOT be in the index entry
        assert "description" not in entry


# ---------------------------------------------------------------------------
# create_entity tests
# ---------------------------------------------------------------------------
class TestCreateEntity:
    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_create_idea(self, mock_rebuild, user_id, sample_idea_data):
        result = await md_storage.create_entity(user_id, "idea", sample_idea_data)

        assert result["name"] == "My Startup Idea"
        assert result["idea_type"] == "hypothesis"
        assert result["status"] == "active"
        assert result["user_id"] == user_id
        assert "id" in result
        assert "first_seen" in result
        assert "last_seen" in result
        assert result["tags"] == ["startup", "ai"]
        assert result["description"] == "A platform that uses AI to automate things."
        assert result["notes"] == "Early stage thinking."

        # Verify index was updated
        index = md_storage._load_index(user_id, "idea")
        assert result["id"] in index

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_create_content(self, mock_rebuild, user_id, sample_content_data):
        result = await md_storage.create_entity(user_id, "content", sample_content_data)
        assert result["title"] == "Great Blog Post"
        assert result["content_type"] == "article"
        assert result["personal_notes"] == "Really insightful article about ML."

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_create_project(self, mock_rebuild, user_id, sample_project_data):
        result = await md_storage.create_entity(user_id, "project", sample_project_data)
        assert result["name"] == "Side Project Alpha"
        assert result["project_type"] == "personal"

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_create_applies_defaults(self, mock_rebuild, user_id):
        result = await md_storage.create_entity(user_id, "idea", {"name": "Bare Idea"})
        assert result["status"] == "active"  # default for idea

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_create_content_default_status(self, mock_rebuild, user_id):
        result = await md_storage.create_entity(user_id, "content", {"title": "Untitled"})
        assert result["status"] == "want"  # default for content

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_create_index_updated(self, mock_rebuild, user_id, sample_idea_data):
        result = await md_storage.create_entity(user_id, "idea", sample_idea_data)
        index = md_storage._load_index(user_id, "idea")
        entry = index[result["id"]]
        assert entry["name"] == "My Startup Idea"
        assert entry["idea_type"] == "hypothesis"
        assert entry["status"] == "active"
        assert "filename" in entry

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_create_generates_uuid(self, mock_rebuild, user_id):
        result = await md_storage.create_entity(user_id, "idea", {"name": "UUID Test"})
        # Should be a valid UUID
        uuid.UUID(result["id"])  # raises if invalid

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_create_sets_timestamps(self, mock_rebuild, user_id):
        result = await md_storage.create_entity(user_id, "idea", {"name": "Timestamp Test"})
        assert result["first_seen"] == result["last_seen"]
        # Should be ISO format
        assert "T" in result["first_seen"]

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_create_writes_md_file(self, mock_rebuild, user_id, sample_idea_data):
        result = await md_storage.create_entity(user_id, "idea", sample_idea_data)
        index = md_storage._load_index(user_id, "idea")
        entry = index[result["id"]]
        filepath = md_storage._get_entity_dir(user_id, "idea") / entry["filename"]
        assert filepath.exists()


# ---------------------------------------------------------------------------
# get_entity tests
# ---------------------------------------------------------------------------
class TestGetEntity:
    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_get_existing(self, mock_rebuild, user_id, sample_idea_data):
        created = await md_storage.create_entity(user_id, "idea", sample_idea_data)
        fetched = await md_storage.get_entity(user_id, "idea", created["id"])
        assert fetched is not None
        assert fetched["id"] == created["id"]
        assert fetched["name"] == "My Startup Idea"

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_get_nonexistent(self, mock_rebuild, user_id):
        result = await md_storage.get_entity(user_id, "idea", "nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_get_body_fields_merged(self, mock_rebuild, user_id, sample_idea_data):
        created = await md_storage.create_entity(user_id, "idea", sample_idea_data)
        fetched = await md_storage.get_entity(user_id, "idea", created["id"])
        assert "description" in fetched
        assert fetched["description"] == "A platform that uses AI to automate things."
        assert "notes" in fetched
        assert fetched["notes"] == "Early stage thinking."

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_get_returns_all_frontmatter(self, mock_rebuild, user_id, sample_idea_data):
        created = await md_storage.create_entity(user_id, "idea", sample_idea_data)
        fetched = await md_storage.get_entity(user_id, "idea", created["id"])
        assert fetched["type"] == "idea"
        assert fetched["user_id"] == user_id
        assert "first_seen" in fetched
        assert "last_seen" in fetched


# ---------------------------------------------------------------------------
# list_entities tests
# ---------------------------------------------------------------------------
class TestListEntities:
    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_list_empty(self, mock_rebuild, user_id):
        items, total = await md_storage.list_entities(user_id, "idea")
        assert items == []
        assert total == 0

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_list_returns_all(self, mock_rebuild, user_id):
        await md_storage.create_entity(user_id, "idea", {"name": "Idea 1"})
        await md_storage.create_entity(user_id, "idea", {"name": "Idea 2"})
        items, total = await md_storage.list_entities(user_id, "idea")
        assert total == 2
        assert len(items) == 2

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_list_filtered_by_status(self, mock_rebuild, user_id):
        await md_storage.create_entity(user_id, "idea", {"name": "Active", "status": "active"})
        await md_storage.create_entity(user_id, "idea", {"name": "Archived", "status": "archived"})
        items, total = await md_storage.list_entities(user_id, "idea", status="active")
        assert total == 1
        assert items[0]["name"] == "Active"

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_list_filtered_by_tags(self, mock_rebuild, user_id):
        await md_storage.create_entity(user_id, "idea", {"name": "AI Idea", "tags": ["ai", "ml"]})
        await md_storage.create_entity(user_id, "idea", {"name": "Web Idea", "tags": ["web"]})
        items, total = await md_storage.list_entities(user_id, "idea", tags=["ai"])
        assert total == 1
        assert items[0]["name"] == "AI Idea"

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_list_tags_match_any(self, mock_rebuild, user_id):
        """Tags filter should match if ANY tag overlaps."""
        await md_storage.create_entity(user_id, "idea", {"name": "A", "tags": ["ai", "ml"]})
        await md_storage.create_entity(user_id, "idea", {"name": "B", "tags": ["web", "ml"]})
        await md_storage.create_entity(user_id, "idea", {"name": "C", "tags": ["design"]})
        items, total = await md_storage.list_entities(user_id, "idea", tags=["ml"])
        assert total == 2

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_list_filtered_by_subtype(self, mock_rebuild, user_id):
        await md_storage.create_entity(user_id, "idea", {"name": "Hyp", "idea_type": "hypothesis"})
        await md_storage.create_entity(user_id, "idea", {"name": "Exp", "idea_type": "experiment"})
        items, total = await md_storage.list_entities(user_id, "idea", idea_type="hypothesis")
        assert total == 1
        assert items[0]["name"] == "Hyp"

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_list_paginated(self, mock_rebuild, user_id):
        for i in range(5):
            await md_storage.create_entity(user_id, "idea", {"name": f"Idea {i}"})
        items, total = await md_storage.list_entities(user_id, "idea", limit=2, offset=0)
        assert total == 5
        assert len(items) == 2

        items2, total2 = await md_storage.list_entities(user_id, "idea", limit=2, offset=2)
        assert total2 == 5
        assert len(items2) == 2

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_list_returns_full_entity_dicts(self, mock_rebuild, user_id):
        await md_storage.create_entity(user_id, "idea", {
            "name": "Full Idea",
            "description": "Full description",
            "notes": "Some notes",
        })
        items, total = await md_storage.list_entities(user_id, "idea")
        assert total == 1
        # Should have body fields merged in
        assert "description" in items[0]
        assert items[0]["description"] == "Full description"

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_list_pagination_past_end(self, mock_rebuild, user_id):
        await md_storage.create_entity(user_id, "idea", {"name": "Only One"})
        items, total = await md_storage.list_entities(user_id, "idea", limit=10, offset=5)
        assert total == 1
        assert len(items) == 0


# ---------------------------------------------------------------------------
# update_entity tests
# ---------------------------------------------------------------------------
class TestUpdateEntity:
    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_update_fields_changed(self, mock_rebuild, user_id, sample_idea_data):
        created = await md_storage.create_entity(user_id, "idea", sample_idea_data)
        updated = await md_storage.update_entity(
            user_id, "idea", created["id"], {"name": "Renamed Idea", "status": "archived"}
        )
        assert updated is not None
        assert updated["name"] == "Renamed Idea"
        assert updated["status"] == "archived"

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_update_nonexistent_returns_none(self, mock_rebuild, user_id):
        result = await md_storage.update_entity(user_id, "idea", "no-such-id", {"name": "X"})
        assert result is None

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_update_refreshes_last_seen(self, mock_rebuild, user_id, sample_idea_data):
        created = await md_storage.create_entity(user_id, "idea", sample_idea_data)
        original_last_seen = created["last_seen"]

        # Small delay to ensure timestamp differs
        time.sleep(0.05)

        updated = await md_storage.update_entity(
            user_id, "idea", created["id"], {"confidence": 0.9}
        )
        assert updated["last_seen"] >= original_last_seen

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_update_syncs_index(self, mock_rebuild, user_id, sample_idea_data):
        created = await md_storage.create_entity(user_id, "idea", sample_idea_data)
        await md_storage.update_entity(
            user_id, "idea", created["id"], {"name": "New Name", "status": "archived"}
        )
        index = md_storage._load_index(user_id, "idea")
        entry = index[created["id"]]
        assert entry["name"] == "New Name"
        assert entry["status"] == "archived"

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_update_body_fields(self, mock_rebuild, user_id, sample_idea_data):
        created = await md_storage.create_entity(user_id, "idea", sample_idea_data)
        updated = await md_storage.update_entity(
            user_id, "idea", created["id"], {"description": "Updated description"}
        )
        assert updated["description"] == "Updated description"
        # notes should remain unchanged
        assert updated["notes"] == "Early stage thinking."

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_update_preserves_first_seen(self, mock_rebuild, user_id, sample_idea_data):
        created = await md_storage.create_entity(user_id, "idea", sample_idea_data)
        original_first_seen = created["first_seen"]
        updated = await md_storage.update_entity(
            user_id, "idea", created["id"], {"name": "Changed"}
        )
        assert updated["first_seen"] == original_first_seen

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_update_persists_to_disk(self, mock_rebuild, user_id, sample_idea_data):
        created = await md_storage.create_entity(user_id, "idea", sample_idea_data)
        await md_storage.update_entity(
            user_id, "idea", created["id"], {"name": "Persisted Name"}
        )
        # Re-read from disk
        fetched = await md_storage.get_entity(user_id, "idea", created["id"])
        assert fetched["name"] == "Persisted Name"


# ---------------------------------------------------------------------------
# delete_entity tests
# ---------------------------------------------------------------------------
class TestDeleteEntity:
    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_delete_existing(self, mock_rebuild, user_id, sample_idea_data):
        created = await md_storage.create_entity(user_id, "idea", sample_idea_data)
        result = await md_storage.delete_entity(user_id, "idea", created["id"])
        assert result is True

        # Should be gone from index
        index = md_storage._load_index(user_id, "idea")
        assert created["id"] not in index

        # Should be gone from disk
        fetched = await md_storage.get_entity(user_id, "idea", created["id"])
        assert fetched is None

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_delete_removes_from_index(self, mock_rebuild, user_id, sample_idea_data):
        created = await md_storage.create_entity(user_id, "idea", sample_idea_data)
        eid = created["id"]
        await md_storage.delete_entity(user_id, "idea", eid)
        index = md_storage._load_index(user_id, "idea")
        assert eid not in index

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_delete_nonexistent_returns_false(self, mock_rebuild, user_id):
        result = await md_storage.delete_entity(user_id, "idea", "nonexistent-id")
        assert result is False

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_delete_removes_md_file(self, mock_rebuild, user_id, sample_idea_data):
        created = await md_storage.create_entity(user_id, "idea", sample_idea_data)
        index = md_storage._load_index(user_id, "idea")
        filename = index[created["id"]]["filename"]
        filepath = md_storage._get_entity_dir(user_id, "idea") / filename
        assert filepath.exists()

        await md_storage.delete_entity(user_id, "idea", created["id"])
        assert not filepath.exists()

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_delete_then_create_same_name(self, mock_rebuild, user_id):
        """After deletion, creating a new entity with the same name should work."""
        created = await md_storage.create_entity(user_id, "idea", {"name": "Reuse Name"})
        await md_storage.delete_entity(user_id, "idea", created["id"])
        new = await md_storage.create_entity(user_id, "idea", {"name": "Reuse Name"})
        assert new["id"] != created["id"]
        items, total = await md_storage.list_entities(user_id, "idea")
        assert total == 1


# ---------------------------------------------------------------------------
# rebuild_index tests
# ---------------------------------------------------------------------------
class TestRebuildIndex:
    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_rebuild_index_from_files(self, mock_rebuild, user_id, sample_idea_data):
        """Create entities, delete the index, rebuild it, and verify correctness."""
        created1 = await md_storage.create_entity(user_id, "idea", sample_idea_data)
        created2 = await md_storage.create_entity(user_id, "idea", {"name": "Second Idea"})

        # Wipe the index
        md_storage._save_index(user_id, "idea", {})
        assert md_storage._load_index(user_id, "idea") == {}

        # Rebuild
        new_index = await md_storage.rebuild_index(user_id, "idea")
        assert created1["id"] in new_index
        assert created2["id"] in new_index
        assert new_index[created1["id"]]["name"] == "My Startup Idea"
        assert new_index[created2["id"]]["name"] == "Second Idea"

    @pytest.mark.asyncio
    async def test_rebuild_index_empty_dir(self, user_id):
        """Rebuild on an empty directory returns an empty index."""
        new_index = await md_storage.rebuild_index(user_id, "idea")
        assert new_index == {}


# ---------------------------------------------------------------------------
# _rebuild_collection_and_tree / tree generation tests
# ---------------------------------------------------------------------------
class TestRebuildCollectionAndTree:
    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_rebuild_collection_and_tree(self, mock_rebuild, user_id, sample_idea_data):
        """Create entities, run rebuild manually, verify tree file exists."""
        await md_storage.create_entity(user_id, "idea", sample_idea_data)
        await md_storage.create_entity(user_id, "idea", {"name": "Second Idea", "tags": ["test"]})

        # Run the collection + tree rebuild directly (bypass debounce)
        await _rebuild_collection(user_id, "idea")
        await _rebuild_tree(user_id, "idea")

        entity_dir = md_storage._get_entity_dir(user_id, "idea")
        collection_path = entity_dir / "_collection.md"
        tree_path = entity_dir / "_tree.json"

        assert collection_path.exists()
        assert tree_path.exists()

        # Tree should be valid JSON
        tree = json.loads(tree_path.read_text(encoding="utf-8"))
        assert "structure" in tree
        assert "doc_name" in tree

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_rebuild_collection_content(self, mock_rebuild, user_id, sample_idea_data):
        """Collection file should contain entity names."""
        await md_storage.create_entity(user_id, "idea", sample_idea_data)

        await _rebuild_collection(user_id, "idea")

        entity_dir = md_storage._get_entity_dir(user_id, "idea")
        collection_path = entity_dir / "_collection.md"
        content = collection_path.read_text(encoding="utf-8")

        assert "My Startup Idea" in content
        assert "# Ideas" in content

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_fallback_tree_structure(self, mock_rebuild, user_id, sample_idea_data):
        """Fallback tree groups by status -> subtype."""
        await md_storage.create_entity(user_id, "idea", sample_idea_data)
        await md_storage.create_entity(
            user_id, "idea",
            {"name": "Archived Idea", "status": "archived", "idea_type": "experiment"},
        )

        tree = _build_fallback_tree(user_id, "idea")
        assert tree["doc_name"] == f"{user_id}-idea"
        assert len(tree["structure"]) >= 1  # at least one status group

        # Flatten all titles to check entity presence
        all_titles = []
        for status_node in tree["structure"]:
            for subtype_node in status_node.get("children", []):
                for entity_node in subtype_node.get("children", []):
                    all_titles.append(entity_node["title"])
        assert any("My Startup Idea" in t for t in all_titles)
        assert any("Archived Idea" in t for t in all_titles)


# ---------------------------------------------------------------------------
# _load_tree tests
# ---------------------------------------------------------------------------
class TestLoadTree:
    def test_load_tree_missing(self, user_id):
        """Returns None when no tree file exists."""
        result = _load_tree(user_id, "idea")
        assert result is None

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_load_tree_after_rebuild(self, mock_rebuild, user_id, sample_idea_data):
        """After rebuild, _load_tree should return the tree dict."""
        await md_storage.create_entity(user_id, "idea", sample_idea_data)
        await _rebuild_collection(user_id, "idea")
        await _rebuild_tree(user_id, "idea")

        tree = _load_tree(user_id, "idea")
        assert tree is not None
        assert "structure" in tree

    def test_load_tree_corrupt_json(self, user_id):
        """Returns None for corrupt JSON files."""
        entity_dir = md_storage._get_entity_dir(user_id, "idea")
        tree_path = entity_dir / "_tree.json"
        tree_path.write_text("not valid json {{", encoding="utf-8")
        result = _load_tree(user_id, "idea")
        assert result is None


# ---------------------------------------------------------------------------
# search_entities tests
# ---------------------------------------------------------------------------
class TestSearchEntities:
    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_search_entities_basic(self, mock_rebuild, user_id):
        """Search finds entities matching by display name."""
        await md_storage.create_entity(user_id, "idea", {"name": "Machine Learning Pipeline"})
        await md_storage.create_entity(user_id, "idea", {"name": "Web App Design"})
        await md_storage.create_entity(user_id, "idea", {"name": "ML Model Training"})

        results = await search_entities(user_id, "idea", "machine learning")
        assert len(results) >= 1
        names = [r["name"] for r in results]
        assert "Machine Learning Pipeline" in names

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_search_entities_empty(self, mock_rebuild, user_id):
        """Search on empty collection returns []."""
        results = await search_entities(user_id, "idea", "anything")
        assert results == []

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_search_entities_by_tags(self, mock_rebuild, user_id):
        """Search matches tag content."""
        await md_storage.create_entity(
            user_id, "idea",
            {"name": "Unnamed Project", "tags": ["blockchain", "defi"]},
        )
        await md_storage.create_entity(
            user_id, "idea",
            {"name": "Another Thing", "tags": ["cooking"]},
        )

        results = await search_entities(user_id, "idea", "blockchain")
        assert len(results) >= 1
        assert results[0]["name"] == "Unnamed Project"

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_search_entities_no_match(self, mock_rebuild, user_id):
        """Search with non-matching query returns []."""
        await md_storage.create_entity(user_id, "idea", {"name": "Alpha"})
        results = await search_entities(user_id, "idea", "zzzznotfound")
        assert results == []

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_search_entities_respects_limit(self, mock_rebuild, user_id):
        """Search returns at most `limit` results."""
        for i in range(10):
            await md_storage.create_entity(
                user_id, "idea", {"name": f"AI Project {i}", "tags": ["ai"]},
            )

        results = await search_entities(user_id, "idea", "ai", limit=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_search_entities_by_status(self, mock_rebuild, user_id):
        """Search can match on status field."""
        await md_storage.create_entity(
            user_id, "idea", {"name": "Done Thing", "status": "archived"},
        )
        await md_storage.create_entity(
            user_id, "idea", {"name": "Active Thing", "status": "active"},
        )

        results = await search_entities(user_id, "idea", "archived")
        assert len(results) >= 1
        assert results[0]["name"] == "Done Thing"

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_search_entities_by_subtype(self, mock_rebuild, user_id):
        """Search can match on subtype field."""
        await md_storage.create_entity(
            user_id, "idea",
            {"name": "Hyp Idea", "idea_type": "hypothesis"},
        )
        await md_storage.create_entity(
            user_id, "idea",
            {"name": "Exp Idea", "idea_type": "experiment"},
        )

        results = await search_entities(user_id, "idea", "hypothesis")
        assert len(results) >= 1
        assert results[0]["name"] == "Hyp Idea"

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_search_entities_ranking(self, mock_rebuild, user_id):
        """Entity matching on name should rank higher than tag-only match."""
        await md_storage.create_entity(
            user_id, "idea",
            {"name": "Blockchain Platform", "tags": ["crypto"]},
        )
        await md_storage.create_entity(
            user_id, "idea",
            {"name": "Cooking App", "tags": ["blockchain"]},
        )

        results = await search_entities(user_id, "idea", "blockchain")
        assert len(results) == 2
        # Name match (3.0) should outrank tag match (2.0)
        assert results[0]["name"] == "Blockchain Platform"

    @pytest.mark.asyncio
    @patch.object(md_storage, "_rebuild_collection_and_tree", new_callable=AsyncMock)
    async def test_search_empty_query(self, mock_rebuild, user_id):
        """Empty query returns []."""
        await md_storage.create_entity(user_id, "idea", {"name": "Something"})
        results = await search_entities(user_id, "idea", "")
        assert results == []
