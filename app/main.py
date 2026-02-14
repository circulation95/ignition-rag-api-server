from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.api.v1.router import api_router
from app.core.config import settings
from app.graph.builder import build_graph
from app.services.vectorstore import init_retriever
from app.services.checkpointer import get_checkpointer_context
from langgraph.checkpoint.memory import MemorySaver


# LangSmith 추적 활성화
if settings.langsmith_tracing:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_ENDPOINT"] = settings.langsmith_endpoint
    os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
    print(f"[LangSmith] 추적 활성화됨 - Project: {settings.langsmith_project}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n[System] 서버 초기화 중...")
    try:
        loaded = init_retriever()
        if loaded:
            print("[System] 벡터 DB 로드 완료.")
        else:
            print("[System] 벡터 DB 없음. RAG 비활성.")
    except Exception as exc:
        print(f"[Warning] 벡터 DB 로드 실패: {exc}")

    # Get checkpointer context (use_memory=False for production persistence)
    checkpointer_ctx = get_checkpointer_context(use_memory=False)

    # If using AsyncSqliteSaver, enter its context manager
    if not isinstance(checkpointer_ctx, MemorySaver):
        async with checkpointer_ctx as checkpointer:
            app.state.checkpointer = checkpointer
            app.state.app_graph = build_graph(checkpointer=checkpointer)
            yield
    else:
        # MemorySaver doesn't need context manager
        app.state.checkpointer = checkpointer_ctx
        app.state.app_graph = build_graph(checkpointer=checkpointer_ctx)
        yield

    print("[System] 서버 종료")


ALLOWED_ORIGINS = ["http://localhost:8089", "http://127.0.0.1:8089"]

app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.options("/{full_path:path}")
async def preflight_handler():
    return Response(status_code=204)
app.include_router(api_router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
