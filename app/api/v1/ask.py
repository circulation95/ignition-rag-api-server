from fastapi import APIRouter, Request
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
    question_text = request.get_question_text()

    if not question_text:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422, detail="Either 'question' or 'query' field is required"
        )

    print(f"\nQ : {question_text}")

    app_graph = fastapi_request.app.state.app_graph
    inputs = {"messages": [HumanMessage(content=question_text)]}
    config = RunnableConfig(
        configurable={"thread_id": request.thread_id},
        recursion_limit=30,
    )

    result = await app_graph.ainvoke(inputs, config=config)

    last_message = result["messages"][-1]
    final_answer = (
        last_message.content
        if isinstance(last_message, AIMessage)
        else "응답을 생성하지 못했습니다."
    )

    return {
        "intent": result.get("intent_category"),
        "answer": final_answer,
    }
