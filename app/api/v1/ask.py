from fastapi import APIRouter, Request
from pydantic import BaseModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig


router = APIRouter()


class QueryRequest(BaseModel):
    question: str
    thread_id: str = "default_user"


@router.post("/ask")
async def ask(request: QueryRequest, fastapi_request: Request):
    print(f"\nQ : {request.question}")

    app_graph = fastapi_request.app.state.app_graph
    inputs = {"messages": [HumanMessage(content=request.question)]}
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

