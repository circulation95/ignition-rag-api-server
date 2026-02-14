"""
In-memory storage for pending actions.

For production, this should be replaced with a database (Redis, PostgreSQL, etc.)
to persist across server restarts and support distributed deployments.
"""

from typing import Dict, Optional
from app.graph.state import PendingAction

# In-memory storage: action_id -> PendingAction
_pending_actions: Dict[str, PendingAction] = {}


def store_pending_action(action: PendingAction) -> None:
    """Store a pending action."""
    _pending_actions[action.id] = action


def get_pending_action(action_id: str) -> Optional[PendingAction]:
    """Retrieve a pending action by ID."""
    return _pending_actions.get(action_id)


def update_pending_action(action: PendingAction) -> None:
    """Update a pending action's status."""
    if action.id in _pending_actions:
        _pending_actions[action.id] = action


def delete_pending_action(action_id: str) -> None:
    """Remove a pending action from storage."""
    if action_id in _pending_actions:
        del _pending_actions[action_id]


def list_pending_actions() -> list[PendingAction]:
    """List all pending actions."""
    return [action for action in _pending_actions.values() if action.status == "pending"]
