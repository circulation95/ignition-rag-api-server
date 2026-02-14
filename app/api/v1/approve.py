"""
Approval endpoint for human-in-the-loop safety controls.

Allows operators to approve or reject pending write operations.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.approval_storage import (
    get_pending_action,
    list_pending_actions,
    update_pending_action,
)
from app.services.opc import get_opc_client

router = APIRouter()


class ApprovalRequest(BaseModel):
    """Request to approve or reject a pending action."""

    action_id: str
    approved: bool
    operator: str
    notes: Optional[str] = None


class ApprovalResponse(BaseModel):
    """Response after approval decision."""

    status: str
    action_id: str
    message: str
    result: Optional[dict] = None


@router.post("/approve", response_model=ApprovalResponse)
async def approve_action(request: ApprovalRequest):
    """
    Approve or reject a pending write operation.

    Args:
        request: Approval request with action_id, approved flag, and operator info

    Returns:
        ApprovalResponse with execution result

    Raises:
        HTTPException: If action not found or already processed
    """
    # Retrieve pending action
    action = get_pending_action(request.action_id)

    if not action:
        raise HTTPException(status_code=404, detail=f"Action {request.action_id} not found")

    # Check if already processed
    if action.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Action {request.action_id} already {action.status}",
        )

    if request.approved:
        # Execute the write operation
        try:
            opc_client = get_opc_client()
            result = await opc_client.write_tag(action.tag_path, action.value)

            # Update action status
            action.status = "executed"
            update_pending_action(action)

            # Log approval (in production, save to database with timestamp and operator)
            print(
                f"[Approval] Action {action.id} APPROVED by {request.operator} "
                f"at {datetime.now().isoformat()}"
            )
            print(f"[Approval] Executed: {action.tag_path} -> {action.value}")
            if request.notes:
                print(f"[Approval] Notes: {request.notes}")

            return ApprovalResponse(
                status="executed",
                action_id=action.id,
                message=f"Write operation executed successfully. Tag {action.tag_path} set to {action.value}",
                result={
                    "tag_path": action.tag_path,
                    "value": action.value,
                    "executed_at": datetime.now().isoformat(),
                    "operator": request.operator,
                    "opc_result": result,
                },
            )

        except Exception as e:
            # Mark as failed
            action.status = "rejected"
            update_pending_action(action)

            raise HTTPException(
                status_code=500,
                detail=f"Failed to execute write operation: {str(e)}",
            )

    else:
        # Reject the action
        action.status = "rejected"
        update_pending_action(action)

        # Log rejection
        print(
            f"[Approval] Action {action.id} REJECTED by {request.operator} "
            f"at {datetime.now().isoformat()}"
        )
        if request.notes:
            print(f"[Approval] Rejection reason: {request.notes}")

        return ApprovalResponse(
            status="rejected",
            action_id=action.id,
            message=f"Write operation rejected by {request.operator}",
        )


@router.get("/pending")
async def list_pending():
    """
    List all pending actions awaiting approval.

    Returns:
        List of pending actions with details
    """
    pending = list_pending_actions()

    return {
        "count": len(pending),
        "actions": [
            {
                "id": action.id,
                "tag_path": action.tag_path,
                "value": action.value,
                "risk_level": action.risk_level,
                "requested_at": action.requested_at.isoformat(),
                "reason": action.reason,
            }
            for action in pending
        ],
    }
