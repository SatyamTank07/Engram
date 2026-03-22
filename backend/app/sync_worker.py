"""
Background worker that retries failed embedding syncs.

Polls the pending_embedding_syncs table and processes entries
with exponential backoff. Runs as an asyncio task during app lifespan.
"""

import asyncio
import logging
from datetime import datetime, timezone

from fastapi.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

# How often the worker checks for pending syncs
POLL_INTERVAL_SECONDS = 30

# Backoff multipliers: retry_count -> delay in seconds
_BACKOFF_SECONDS = [30, 60, 120, 240, 480]


def _get_backoff(retry_count: int) -> int:
    """Return backoff delay in seconds for a given retry count."""
    if retry_count < len(_BACKOFF_SECONDS):
        return _BACKOFF_SECONDS[retry_count]
    return _BACKOFF_SECONDS[-1]


async def _process_pending_syncs():
    """Fetch and process all due pending syncs."""
    from . import vector_db, embedding_service, graph_db

    pending = await run_in_threadpool(vector_db.get_pending_syncs)
    if not pending:
        return

    # Dispatch tables for multi-entity support
    _delete_funcs = {
        "person": vector_db.delete_embedding,
        "idea": vector_db.delete_idea_embedding,
        "content": vector_db.delete_content_embedding,
        "project": vector_db.delete_project_embedding,
    }
    _get_node_funcs = {
        "person": graph_db.get_person_node,
        "idea": graph_db.get_idea_node,
        "content": graph_db.get_content_node,
        "project": graph_db.get_project_node,
    }

    for row in pending:
        sync_id = row["id"]
        entity_id = row["person_id"]  # column name kept for backward compat
        user_id = row["user_id"]
        operation = row["operation"]
        retry_count = row["retry_count"]
        entity_type = row.get("entity_type", "person")

        try:
            if operation == "delete":
                delete_fn = _delete_funcs.get(entity_type, vector_db.delete_embedding)
                await run_in_threadpool(delete_fn, entity_id)
            else:
                get_fn = _get_node_funcs.get(entity_type, graph_db.get_person_node)
                entity = await get_fn(entity_id)
                if entity is None:
                    await run_in_threadpool(vector_db.delete_pending_sync, sync_id)
                    logger.info("[SYNC] %s %s no longer exists, discarding sync", entity_type, entity_id)
                    continue

                if entity_type == "person":
                    text_content, embedding = embedding_service.generate_person_embedding(
                        name=entity.get("name", ""),
                        aliases=entity.get("aliases", []),
                        short_bio=entity.get("short_bio", ""),
                        contacts=entity.get("contacts", {}),
                    )
                    await run_in_threadpool(
                        vector_db.upsert_text_embedding,
                        person_id=entity_id, user_id=user_id,
                        text_content=text_content, embedding=embedding,
                    )
                elif entity_type == "idea":
                    text_content, embedding = embedding_service.generate_idea_embedding(
                        name=entity.get("name", ""),
                        idea_type=entity.get("idea_type"),
                        description=entity.get("description"),
                        tags=entity.get("tags", []),
                        notes=entity.get("notes"),
                    )
                    await run_in_threadpool(
                        vector_db.upsert_idea_text_embedding,
                        idea_id=entity_id, user_id=user_id,
                        text_content=text_content, embedding=embedding,
                    )
                elif entity_type == "content":
                    text_content, embedding = embedding_service.generate_content_embedding(
                        title=entity.get("title", ""),
                        content_type=entity.get("content_type"),
                        author=entity.get("author"),
                        personal_notes=entity.get("personal_notes"),
                        tags=entity.get("tags", []),
                    )
                    await run_in_threadpool(
                        vector_db.upsert_content_text_embedding,
                        content_id=entity_id, user_id=user_id,
                        text_content=text_content, embedding=embedding,
                    )
                elif entity_type == "project":
                    text_content, embedding = embedding_service.generate_project_embedding(
                        name=entity.get("name", ""),
                        project_type=entity.get("project_type"),
                        description=entity.get("description"),
                        goal=entity.get("goal"),
                        tags=entity.get("tags", []),
                        notes=entity.get("notes"),
                    )
                    await run_in_threadpool(
                        vector_db.upsert_project_text_embedding,
                        project_id=entity_id, user_id=user_id,
                        text_content=text_content, embedding=embedding,
                    )

            # Success — remove the pending record
            await run_in_threadpool(vector_db.delete_pending_sync, sync_id)
            logger.info("[SYNC] Successfully synced embedding for %s %s (op=%s)", entity_type, entity_id, operation)

        except Exception as e:
            new_retry = retry_count + 1
            backoff = _get_backoff(new_retry)
            await run_in_threadpool(
                vector_db.update_pending_sync_retry,
                sync_id,
                new_retry,
                backoff,
                str(e),
            )
            logger.warning(
                "[SYNC] Retry %d failed for %s %s: %s. Next retry in %ds",
                new_retry, entity_type, entity_id, e, backoff,
            )


async def run_sync_worker():
    """Long-running loop that processes pending embedding syncs."""
    logger.info("[SYNC] Embedding sync worker started (poll every %ds)", POLL_INTERVAL_SECONDS)
    while True:
        try:
            await _process_pending_syncs()
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            logger.info("[SYNC] Embedding sync worker shutting down")
            return
        except Exception as e:
            logger.error("[SYNC] Unexpected error in sync worker: %s", e)
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
