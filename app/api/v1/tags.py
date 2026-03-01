"""
태그 벡터 스토어 관리 API

Ignition 태그 메타데이터를 ChromaDB에 인덱싱하고 검색하는 엔드포인트.
Ignition Perspective 또는 Gateway Script에서 호출하여 태그 목록을 동기화합니다.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.opc import get_opc_client
from app.services.tag_store import (
    delete_tag_store,
    get_tag_count,
    get_tag_store,
    ingest_tags,
    init_tag_store,
    search_tags,
)

router = APIRouter()


# ── Request/Response 모델 ──────────────────────────────────────────


class TagSearchRequest(BaseModel):
    """태그 검색 요청 (POST 방식)"""

    query: str
    k: int = 3


class TagCandidateResponse(BaseModel):
    """검색 결과 태그 후보"""

    tag_path: str
    display_name: str
    description: str
    tag_type: str
    score: float


# ── 엔드포인트 ────────────────────────────────────────────────────


@router.post("/sync")
async def sync_tags_from_opc(provider: str = "[default]"):
    """
    Ignition OPC UA 서버에서 태그 목록을 직접 읽어와 벡터 스토어에 인덱싱.
    
    Args:
        provider: 검색할 Tag Provider (예: "[default]")
        
    Returns:
        인덱싱된 태그 수와 현재 총 태그 수
    """
    if not get_tag_store():
        # 태그 스토어가 초기화되지 않았으면 재초기화 시도
        success = init_tag_store()
        if not success:
            raise HTTPException(
                status_code=503,
                detail="태그 벡터 스토어를 초기화할 수 없습니다. 서버 로그를 확인하세요.",
            )

    opc_client = get_opc_client()
    try:
        tags = await opc_client.get_all_tags(provider=provider)
        if not tags:
            return {
                "status": "warning",
                "indexed": 0,
                "total": get_tag_count(),
                "message": (
                    f"OPC UA에서 태그를 찾을 수 없습니다. Provider: {provider}. "
                    "Ignition Gateway에서 해당 Tag Provider의 OPC UA 노출이 활성화되어 있는지 확인하세요. "
                    "(Config → Tags → Tag Providers → [default] → OPC UA Expose)"
                ),
            }
            
        indexed_count = ingest_tags(tags)
        
        return {
            "status": "ok",
            "indexed": indexed_count,
            "total": get_tag_count(),
            "message": f"{indexed_count}개 태그 인덱싱 완료 (전체 {get_tag_count()}개)",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"OPC UA 태그 동기화 실패: {str(e)}",
        )


@router.get("/search")
async def search_tags_get(query: str, k: int = 3):
    """
    태그 검색 (GET 방식).

    Args:
        query: 검색 쿼리 (예: "FAN1", "Fan1을 켜줘", "라인1 팬")
        k: 반환할 최대 결과 수 (기본값 3)

    Returns:
        유사도 순 태그 후보 리스트
    """
    if not get_tag_store():
        raise HTTPException(status_code=503, detail="태그 벡터 스토어가 초기화되지 않았습니다.")

    candidates = search_tags(query, k=k)

    return {
        "query": query,
        "count": len(candidates),
        "candidates": [
            {
                "tag_path": c.tag_path,
                "display_name": c.display_name,
                "description": c.description,
                "tag_type": c.tag_type,
                "score": c.score,
            }
            for c in candidates
        ],
    }


@router.get("/status")
async def tag_store_status():
    """태그 벡터 스토어 상태 확인"""
    store = get_tag_store()
    count = get_tag_count()

    return {
        "initialized": store is not None,
        "tag_count": count,
        "status": "ready" if (store and count > 0) else ("empty" if store else "not_initialized"),
    }


@router.delete("/")
async def clear_tag_store():
    """
    태그 벡터 스토어 전체 초기화 (주의: 모든 태그 삭제).

    Ignition 태그 구조가 변경된 경우 이 엔드포인트로 초기화 후 재인덱싱하세요.
    """
    success = delete_tag_store()

    if success:
        # 빈 컬렉션으로 재초기화
        init_tag_store()
        return {"status": "ok", "message": "태그 스토어 초기화 완료"}
    else:
        raise HTTPException(status_code=404, detail="태그 스토어가 초기화되지 않았거나 이미 비어있습니다.")

