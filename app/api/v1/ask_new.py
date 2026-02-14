"""
Modern ask endpoint with LangGraph 1.x interrupt support.

Handles both normal execution and interrupted (HITL) states.
"""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, field_validator
from typing import Optional
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

router = APIRouter()


class QueryRequest(BaseModel):
    question: Optional[str] = None
    query: Optional[str] = None
    thread_id: str = "default_user"

    @field_validator("question", mode="before")
    @classmethod
    def validate_question(cls, v, info):
        # question이 없으면 query 값을 사용
        if v is None and info.data.get("query"):
            return info.data.get("query")
        return v

    def get_question_text(self) -> str:
        """question 또는 query 필드에서 질문 텍스트 가져오기"""
        return self.question or self.query or ""


@router.post("/ask")
async def ask(request: QueryRequest, fastapi_request: Request):
    """
    Process user query with support for LangGraph interrupts.

    When a write operation is requested, the graph will pause (interrupt)
    and return the pending action details. The client should then call
    /api/v1/approve to resume execution.

    Returns:
        - Normal response: intent and answer
        - Interrupted response: intent, answer, and pending_action details
    """
    question_text = request.get_question_text()

    if not question_text:
        raise HTTPException(
            status_code=422,
            detail="Either 'question' or 'query' field is required"
        )

    print(f"\n[Ask API] Question: {question_text}")
    print(f"[Ask API] Thread ID: {request.thread_id}")

    app_graph = fastapi_request.app.state.app_graph
    inputs = {"messages": [HumanMessage(content=question_text)]}
    config = RunnableConfig(
        configurable={"thread_id": request.thread_id},
        recursion_limit=30,
    )

    try:
        # Invoke the graph
        result = await app_graph.ainvoke(inputs, config=config)

        # Get the final state snapshot to check for interrupts
        state_snapshot = app_graph.get_state(config)

        print(f"[Ask API] State snapshot next: {state_snapshot.next}")
        print(f"[Ask API] Interrupted: {state_snapshot.tasks}")

        # Check if the graph was interrupted
        is_interrupted = (
            state_snapshot.tasks and
            len(state_snapshot.tasks) > 0 and
            hasattr(state_snapshot.tasks[0], 'interrupts') and
            state_snapshot.tasks[0].interrupts
        )

        # Build response
        last_message = result["messages"][-1]
        final_answer = (
            last_message.content
            if isinstance(last_message, AIMessage)
            else "응답을 생성하지 못했습니다."
        )

        response = {
            "intent": result.get("intent_category"),
            "answer": final_answer,
            "thread_id": request.thread_id,
        }

        # If interrupted, include the interrupt details
        if is_interrupted:
            print("[Ask API] Graph was interrupted - pending approval")

            # Extract interrupt value
            interrupt_data = state_snapshot.tasks[0].interrupts[0]

            response["status"] = "pending_approval"
            response["pending_action"] = {
                "action_id": interrupt_data.get("action_id"),
                "tag_path": interrupt_data.get("tag_path"),
                "value": interrupt_data.get("value"),
                "risk_level": interrupt_data.get("risk_level"),
                "requested_at": interrupt_data.get("requested_at"),
                "message": interrupt_data.get("message"),
                "approval_url": "/api/v1/approve",
                "state_url": f"/api/v1/state/{request.thread_id}",
            }
        else:
            response["status"] = "completed"

            # Legacy: Check for pending_actions in state (backward compatibility)
            pending_actions = result.get("pending_actions")
            if pending_actions and len(pending_actions) > 0:
                latest_pending = pending_actions[-1]
                response["pending_action"] = {
                    "id": latest_pending.id,
                    "tag": latest_pending.tag_path,
                    "value": latest_pending.value,
                    "risk_level": latest_pending.risk_level,
                    "approval_url": "/api/v1/approve",
                    "requested_at": latest_pending.requested_at.isoformat(),
                }

        return response

    except Exception as e:
        print(f"[Ask API] Error: {e}")
        import traceback
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to process query: {str(e)}"
        )
