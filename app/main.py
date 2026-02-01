from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.api.v1.router import api_router
from app.core.config import settings
from app.graph.builder import build_graph
from app.services.vectorstore import init_retriever


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

    app.state.app_graph = build_graph()
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
