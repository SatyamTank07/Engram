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

    for row in pending:
        sync_id = row["id"]
        person_id = row["person_id"]
        user_id = row["user_id"]
        operation = row["operation"]
        retry_count = row["retry_count"]

        try:
            if operation == "delete":
                await run_in_threadpool(vector_db.delete_embedding, person_id)
            else:
                # upsert: fetch person from Neo4j, regenerate embedding
                person = await graph_db.get_person_node(person_id)
                if person is None:
                    # Person was deleted from Neo4j; discard this sync
                    await run_in_threadpool(vector_db.delete_pending_sync, sync_id)
                    logger.info("[SYNC] Person %s no longer exists, discarding sync", person_id)
                    continue

                text_content, embedding = embedding_service.generate_person_embedding(
                    name=person.get("name", ""),
                    aliases=person.get("aliases", []),
                    short_bio=person.get("short_bio", ""),
                    contacts=person.get("contacts", {}),
                )
                await run_in_threadpool(
                    vector_db.upsert_text_embedding,
                    person_id=person_id,
                    user_id=user_id,
                    text_content=text_content,
                    embedding=embedding,
                )

            # Success — remove the pending record
            await run_in_threadpool(vector_db.delete_pending_sync, sync_id)
            logger.info("[SYNC] Successfully synced embedding for person %s (op=%s)", person_id, operation)

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
                "[SYNC] Retry %d failed for person %s: %s. Next retry in %ds",
                new_retry, person_id, e, backoff,
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
