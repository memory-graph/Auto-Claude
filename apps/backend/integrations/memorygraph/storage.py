"""
Storage Integration for MemoryGraph
====================================

Saves session insights to MemoryGraph after each session.
Async, non-blocking - doesn't slow down session completion.
"""

import logging
from pathlib import Path

from .client import MemoryGraphClient
from .extractor import InsightExtractor
from .relationships import infer_relationships

logger = logging.getLogger(__name__)

# Default importance scores by memory type
FALLBACK_IMPORTANCE = 0.7  # Used when type not in DEFAULT_IMPORTANCE
DEFAULT_IMPORTANCE = {
    "problem": 0.7,
    "error": 0.8,
    "solution": 0.8,
    "code_pattern": 0.6,
}


async def _store_memories(
    memories: list[dict],
    client: MemoryGraphClient,
    project_tags: list[str],
    memory_label: str,
) -> list[dict]:
    """
    Store a list of memories to MemoryGraph.

    Does not mutate the input memories - creates copies with added IDs.

    Args:
        memories: List of memory dicts to store
        client: MemoryGraphClient instance
        project_tags: Tags to add to each memory
        memory_label: Label for logging (e.g., "problem", "solution")

    Returns:
        List of successfully stored memories with IDs added
    """
    stored = []
    for memory in memories:
        try:
            # Merge tags without mutating original
            original_tags = memory.get("tags", [])
            merged_tags = list(set(original_tags + project_tags))

            memory_type = memory["type"]
            default_importance = DEFAULT_IMPORTANCE.get(memory_type, FALLBACK_IMPORTANCE)

            memory_id = await client.store(
                memory_type=memory_type,
                title=memory["title"],
                content=memory["content"],
                tags=merged_tags,
                importance=memory.get("importance", default_importance),
            )

            if memory_id:
                # Create new dict with ID instead of mutating original
                stored_memory = {**memory, "id": memory_id, "tags": merged_tags}
                stored.append(stored_memory)
                logger.debug(f"Stored {memory_label}: {memory['title']}")
        except Exception as e:
            logger.warning(f"Failed to store {memory_label} '{memory['title']}': {e}")
            continue

    return stored


async def save_to_memorygraph(session_output: dict, project_dir: Path) -> None:
    """
    Extract and store insights from session output.

    Called asynchronously after session ends - doesn't block session completion.
    Gracefully handles errors - logs warnings but never crashes.

    Args:
        session_output: Session output dictionary with keys like:
            - what_failed: list of failure descriptions
            - what_worked: list of success descriptions
            - errors: list of error messages
            - qa_rejections: list of QA rejection reasons
            - fixes_applied: list of fixes that worked
            - patterns_found: list of patterns discovered
        project_dir: Project root directory path

    Returns:
        None - stores to MemoryGraph as side effect
    """
    try:
        # Initialize client and extractor
        client = MemoryGraphClient()
        extractor = InsightExtractor()

        # Add project context to all memories
        project_name = project_dir.name
        project_tags = [f"project:{project_name}"]

        # Extract insights
        logger.debug(f"Extracting insights from session for project: {project_name}")

        problems = extractor.extract_problems(session_output)
        solutions = extractor.extract_solutions(session_output)
        patterns = extractor.extract_patterns(session_output)

        if not (problems or solutions or patterns):
            logger.debug("No insights to store from session")
            return

        logger.debug(
            f"Extracted {len(problems)} problems, {len(solutions)} solutions, "
            f"{len(patterns)} patterns"
        )

        # Store all memory types using helper function
        stored_problems = await _store_memories(
            problems, client, project_tags, "problem"
        )
        stored_solutions = await _store_memories(
            solutions, client, project_tags, "solution"
        )
        stored_patterns = await _store_memories(
            patterns, client, project_tags, "pattern"
        )

        # Create relationships between problems and solutions
        if stored_problems and stored_solutions:
            try:
                await infer_relationships(stored_problems, stored_solutions, client)
                logger.debug(
                    f"Created relationships between {len(stored_solutions)} solutions "
                    f"and {len(stored_problems)} problems"
                )
            except Exception as e:
                logger.warning(f"Failed to create relationships: {e}")

        logger.debug(
            f"Successfully stored session insights: {len(stored_problems)} problems, "
            f"{len(stored_solutions)} solutions, {len(stored_patterns)} patterns"
        )

    except Exception as e:
        # Never crash - just log the error
        logger.warning(f"Failed to save session to MemoryGraph: {e}")
