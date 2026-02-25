import re
import uuid
from typing import Optional

from fastapi import APIRouter, Request
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, field_validator

router = APIRouter()

# USER_SELECTION 접두사: 프론트엔드에서 카드 선택 후 전송하는 포맷
# 예: "USER_SELECTION: [default]Line1/FAN/FAN1 태그를 켜줘"
_USER_SELECTION_PREFIX = "USER_SELECTION: "

# 태그 경로 패턴: [namespace]path/to/tag
_TAG_PATH_PATTERN = re.compile(r"(\[\w+\][\w/\-\.]+)")


class QueryRequest(BaseModel):
    question: Optional[str] = None
    query: Optional[str] = None
    thread_id: Optional[str] = None  # Optional: if not provided, creates new session

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
    question_text = request.get_question_text()

    if not question_text:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422, detail="Either 'question' or 'query' field is required"
        )

    # If no thread_id provided, create a new session
    thread_id = request.thread_id or str(uuid.uuid4())

    # ── USER_SELECTION 처리 ───────────────────────────────────────
    # 프론트엔드에서 태그 카드 선택 후 전송 포맷:
    #   "USER_SELECTION: [default]Line1/FAN/FAN1 태그를 켜줘"
    #
    # 처리:
    # 1. 접두사 제거 → question_text = "[default]Line1/FAN/FAN1 태그를 켜줘"
    # 2. 태그 경로 파싱 → confirmed_tag_path = "[default]Line1/FAN/FAN1"
    # 3. GraphState에 confirmed_tag_path 주입 → Disambiguation 노드 건너뜀
    confirmed_tag_path: Optional[str] = None

    if question_text.startswith(_USER_SELECTION_PREFIX):
        content = question_text[len(_USER_SELECTION_PREFIX):]

        # 태그 경로 추출: [default]Line1/FAN/FAN1
        match = _TAG_PATH_PATTERN.search(content)
        if match:
            confirmed_tag_path = match.group(1)
            print(f"\n[Session: {thread_id}] USER_SELECTION 감지: {confirmed_tag_path}")

        question_text = content  # 접두사 제거 후 질문 사용

    print(f"\n[Session: {thread_id}] Q: {question_text}")

    app_graph = fastapi_request.app.state.app_graph

    # GraphState 초기값: confirmed_tag_path가 있으면 Disambiguation 건너뜀
    inputs: dict = {"messages": [HumanMessage(content=question_text)]}
    if confirmed_tag_path:
        inputs["confirmed_tag_path"] = confirmed_tag_path

    config = RunnableConfig(
        configurable={"thread_id": thread_id},
        recursion_limit=30,
    )

    result = await app_graph.ainvoke(inputs, config=config)

    # ── 태그 Disambiguation 응답 처리 ─────────────────────────────
    # tag_disambiguation_node가 복수 후보를 발견한 경우
    tag_candidates = result.get("tag_candidates")
    if tag_candidates:
        return {
            "thread_id": thread_id,
            "intent": result.get("intent_category"),
            "answer": "여러 태그가 발견되었습니다. 제어하려는 태그를 선택해 주세요.",
            "ui_component": "tag_selection_cards",
            "tag_candidates": tag_candidates,
        }

    # ── 일반 응답 처리 ────────────────────────────────────────────
    last_message = result["messages"][-1]
    final_answer = (
        last_message.content
        if isinstance(last_message, AIMessage)
        else "응답을 생성하지 못했습니다."
    )

    # Build base response with thread_id
    response = {
        "thread_id": thread_id,  # Return thread_id for session management
        "intent": result.get("intent_category"),
        "answer": final_answer,
    }

    # Phase 1: Include pending action if write operation is queued
    pending_actions = result.get("pending_actions")
    if pending_actions and len(pending_actions) > 0:
        # Get the most recent pending action
        latest_pending = pending_actions[-1]

        response["pending_action"] = {
            "id": latest_pending.id,
            "tag": latest_pending.tag_path,
            "value": latest_pending.value,
            "risk_level": latest_pending.risk_level,
            "approval_url": "/approve",
            "requested_at": latest_pending.requested_at.isoformat(),
        }

    return response
