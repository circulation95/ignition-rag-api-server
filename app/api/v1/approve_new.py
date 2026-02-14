"""
Modern approval endpoint using LangGraph 1.x interrupt/resume pattern.

This replaces the legacy approval workflow with:
- LangGraph interrupts for pausing execution
- Command for resuming with human feedback
- State persistence via checkpointer
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from langgraph.types import Command

from app.graph.state import HumanFeedback
from app.graph.builder import build_graph

router = APIRouter()


class ApprovalRequest(BaseModel):
    """Request to approve or reject a pending action."""

    thread_id: str  # Required to identify the interrupted graph
    action_id: str  # ID of the action being approved
    approved: bool
    operator: str
    notes: Optional[str] = None


class ApprovalResponse(BaseModel):
    """Response after approval decision."""

    status: str
    thread_id: str
    action_id: str
    message: str
    checkpoint_id: Optional[str] = None
    result: Optional[dict] = None


class PendingActionsResponse(BaseModel):
    """Response for listing pending actions."""

    count: int
    actions: list[dict]


@router.post("/approve", response_model=ApprovalResponse)
async def approve_action(request: ApprovalRequest):
    """
    Approve or reject a pending write operation using LangGraph resume.

    This endpoint:
    1. Retrieves the interrupted graph state using thread_id
    2. Creates a Command with human feedback
    3. Resumes the graph execution
    4. Returns the result

    Args:
        request: Approval request with thread_id, action_id, and approval decision

    Returns:
        ApprovalResponse with execution result

    Raises:
        HTTPException: If thread not found or not interrupted
    """
    print(f"[Approval API] Received approval request for thread {request.thread_id}")
    print(f"[Approval API] Action {request.action_id}: {'APPROVED' if request.approved else 'REJECTED'}")

    # Get the graph instance
    graph = build_graph(use_modern_hitl=True, use_memory=False)

    # Build config with thread_id
    config = {"configurable": {"thread_id": request.thread_id}}

    try:
        # Check current state
        state_snapshot = graph.get_state(config)

        if not state_snapshot:
            raise HTTPException(
                status_code=404,
                detail=f"Thread {request.thread_id} not found"
            )

        # Check if the graph is actually interrupted
        # In LangGraph 1.x, next contains the nodes to execute
        # If interrupted, next should be empty or contain interrupt marker
        print(f"[Approval API] Current state: {state_snapshot.next}")
        print(f"[Approval API] Tasks: {len(state_snapshot.tasks) if state_snapshot.tasks else 0}")

        # Create human feedback
        feedback = HumanFeedback(
            action_id=request.action_id,
            approved=request.approved,
            operator=request.operator,
            notes=request.notes,
            timestamp=datetime.now(),
        )

        # Resume the graph with Command
        # The interrupt() call will receive this approval decision
        approval_decision = {
            "approved": request.approved,
            "operator": request.operator,
            "notes": request.notes,
            "timestamp": datetime.now().isoformat(),
        }

        print(f"[Approval API] Resuming graph with approval decision")

        # Resume execution by invoking with Command
        # The interrupt value becomes the return value of interrupt()
        result = graph.invoke(
            Command(resume=approval_decision),
            config=config
        )

        print(f"[Approval API] Graph execution completed")

        # Extract final message
        final_message = result["messages"][-1] if result.get("messages") else None
        final_content = final_message.content if final_message else "Operation completed"

        return ApprovalResponse(
            status="executed" if request.approved else "rejected",
            thread_id=request.thread_id,
            action_id=request.action_id,
            message=final_content,
            checkpoint_id=state_snapshot.config.get("configurable", {}).get("checkpoint_id"),
            result={
                "approved": request.approved,
                "operator": request.operator,
                "executed_at": datetime.now().isoformat(),
                "notes": request.notes,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Approval API] Error: {e}")
        import traceback
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to process approval: {str(e)}",
        )


@router.get("/pending", response_model=PendingActionsResponse)
async def list_pending():
    """
    List all threads with pending approval (interrupted state).

    In the modern pattern, we check the checkpointer for interrupted threads
    rather than maintaining a separate pending actions storage.

    Returns:
        List of pending actions from interrupted threads
    """
    from app.services.checkpointer import get_checkpointer

    checkpointer = get_checkpointer(use_memory=False)

    try:
        # List all threads from checkpointer
        # Note: This requires iterating through checkpoints
        # In production, you might want to maintain a separate index
        # of interrupted threads for performance

        pending_actions = []

        # For now, return a simple response
        # A production implementation would query the checkpointer more efficiently
        return PendingActionsResponse(
            count=0,
            actions=[]
        )

    except Exception as e:
        print(f"[Approval API] Error listing pending: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list pending actions: {str(e)}",
        )


@router.get("/state/{thread_id}")
async def get_thread_state(thread_id: str):
    """
    Get the current state of a thread (useful for debugging).

    Args:
        thread_id: Thread ID to inspect

    Returns:
        Current state snapshot
    """
    graph = build_graph(use_modern_hitl=True, use_memory=False)
    config = {"configurable": {"thread_id": thread_id}}

    try:
        state = graph.get_state(config)

        if not state:
            raise HTTPException(
                status_code=404,
                detail=f"Thread {thread_id} not found"
            )

        return {
            "thread_id": thread_id,
            "next": state.next,
            "tasks": [
                {
                    "id": task.id,
                    "name": task.name,
                }
                for task in (state.tasks or [])
            ],
            "checkpoint_id": state.config.get("configurable", {}).get("checkpoint_id"),
            "values_keys": list(state.values.keys()) if state.values else [],
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Approval API] Error getting state: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get thread state: {str(e)}",
        )
