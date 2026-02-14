"""
LangGraph State Persistence with Checkpointer.

Uses SqliteSaver for production-grade state management across restarts.
Supports graph interrupts, breakpoints, and resume operations.
"""

import os
from pathlib import Path
from typing import Optional

from typing import AsyncContextManager

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.checkpoint.memory import MemorySaver

from app.core.config import settings


def get_checkpointer_context(
    use_memory: bool = False,
) -> AsyncContextManager[AsyncSqliteSaver] | MemorySaver:
    """
    Get a LangGraph checkpointer for state persistence.

    Args:
        use_memory: If True, use in-memory checkpointer (for testing)
                   If False, returns AsyncSqliteSaver context manager (production)

    Returns:
        For memory: MemorySaver instance
        For SQLite: AsyncSqliteSaver context manager (use with 'async with')
    """
    if use_memory:
        print("[Checkpointer] Using in-memory checkpointer (testing mode)")
        return MemorySaver()

    # Create data directory if it doesn't exist
    data_dir = Path(getattr(settings, "data_dir", "./data"))
    data_dir.mkdir(parents=True, exist_ok=True)

    db_path = data_dir / "checkpoints.db"

    print(f"[Checkpointer] Using async SQLite checkpointer at {db_path}")

    # Return the context manager - caller must use 'async with' to enter it
    return AsyncSqliteSaver.from_conn_string(str(db_path))


def get_thread_state(
    checkpointer: AsyncSqliteSaver, thread_id: str, checkpoint_id: Optional[str] = None
):
    """
    Retrieve the current state of a thread.

    Args:
        checkpointer: The checkpointer instance
        thread_id: Thread ID to retrieve
        checkpoint_id: Optional specific checkpoint ID (defaults to latest)

    Returns:
        State dict or None if not found
    """
    config = {"configurable": {"thread_id": thread_id}}

    if checkpoint_id:
        config["configurable"]["checkpoint_id"] = checkpoint_id

    try:
        state = checkpointer.get(config)
        return state
    except Exception as e:
        print(f"[Checkpointer] Error retrieving state: {e}")
        return None


def list_thread_checkpoints(checkpointer: AsyncSqliteSaver, thread_id: str):
    """
    List all checkpoints for a thread (useful for debugging).

    Args:
        checkpointer: The checkpointer instance
        thread_id: Thread ID to list checkpoints for

    Returns:
        List of checkpoint metadata
    """
    config = {"configurable": {"thread_id": thread_id}}

    try:
        checkpoints = list(checkpointer.list(config))
        return checkpoints
    except Exception as e:
        print(f"[Checkpointer] Error listing checkpoints: {e}")
        return []
