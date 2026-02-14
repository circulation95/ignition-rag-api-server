from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.api.v1.router import api_router
from app.core.config import settings
from app.graph.builder import build_graph
from app.services.vectorstore import init_retriever


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

    # No checkpointer - state is not persisted (stateless mode)
    print("[Checkpointer] Stateless mode - no state persistence")
    app.state.checkpointer = None
    app.state.app_graph = build_graph(checkpointer=None)
    yield

    print("[System] 서버 종료")


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# CORS configuration - explicit origins for development
origins = [
    "http://localhost:8089",
    "http://127.0.0.1:8089",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(api_router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
