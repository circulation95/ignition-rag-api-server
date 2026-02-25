"""태그 전용 ChromaDB 컬렉션 - 태그 경로 Disambiguation용"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.core.config import settings
from app.services.vectorstore import get_embeddings


@dataclass
class TagCandidate:
    """태그 후보 - 유사도 검색 결과"""

    tag_path: str       # [default]Line1/FAN/FAN1
    display_name: str   # FAN1
    description: str    # Line 1 Fan Motor
    tag_type: str       # Boolean, Float4, etc.
    score: float        # 유사도 점수 (0~1, 높을수록 유사)


_tag_vectorstore: Chroma | None = None


def init_tag_store() -> bool:
    """
    태그 전용 ChromaDB 컬렉션 초기화.

    Returns:
        True: 성공 (태그 있거나 빈 컬렉션 준비됨)
        False: 초기화 실패
    """
    global _tag_vectorstore

    try:
        embeddings = get_embeddings()
        os.makedirs(settings.vectorstore_path, exist_ok=True)

        _tag_vectorstore = Chroma(
            collection_name=settings.chroma_tag_collection_name,
            embedding_function=embeddings,
            persist_directory=settings.vectorstore_path,
        )

        count = _tag_vectorstore._collection.count()
        print(f"[TagStore] 초기화 완료: {count}개 태그 인덱싱됨")
        return True

    except Exception as e:
        print(f"[TagStore] 초기화 실패: {e}")
        _tag_vectorstore = None
        return False


def get_tag_store() -> Optional[Chroma]:
    """현재 태그 벡터스토어 인스턴스 반환"""
    return _tag_vectorstore


def ingest_tags(tags: list[dict]) -> int:
    """
    태그 목록을 ChromaDB에 인덱싱.

    Args:
        tags: 태그 딕셔너리 리스트
              각 항목: {tag_path, display_name, description, tag_type, namespace}

    Returns:
        인덱싱된 태그 수
    """
    if _tag_vectorstore is None:
        print("[TagStore] 태그 스토어 미초기화")
        return 0

    if not tags:
        return 0

    docs = []
    ids = []

    for tag in tags:
        tag_path = tag.get("tag_path", "").strip()
        display_name = tag.get("display_name", "").strip()
        description = tag.get("description", "").strip()
        tag_type = tag.get("tag_type", "").strip()

        if not tag_path:
            continue

        # 임베딩 텍스트: 경로 + 이름 + 설명 조합으로 검색 정확도 향상
        content_parts = [tag_path, display_name, description]
        content = " ".join(p for p in content_parts if p)

        doc = Document(
            page_content=content,
            metadata={
                "tag_path": tag_path,
                "display_name": display_name,
                "description": description,
                "tag_type": tag_type,
            },
        )
        docs.append(doc)
        ids.append(tag_path)  # tag_path를 ID로 사용해 중복 방지 (upsert 동작)

    if not docs:
        return 0

    try:
        # 기존 ID가 있으면 덮어쓰기 (upsert)
        _tag_vectorstore.add_documents(docs, ids=ids)
        print(f"[TagStore] {len(docs)}개 태그 인덱싱 완료")
        return len(docs)
    except Exception as e:
        print(f"[TagStore] 인덱싱 실패: {e}")
        return 0


def search_tags(query: str, k: int = 3) -> list[TagCandidate]:
    """
    쿼리와 유사한 태그 Top K 반환.

    Args:
        query: 검색 쿼리 (사용자 입력 그대로 또는 태그 키워드)
        k: 반환할 최대 결과 수

    Returns:
        유사도 순으로 정렬된 TagCandidate 리스트
    """
    if _tag_vectorstore is None:
        return []

    try:
        count = _tag_vectorstore._collection.count()
        if count == 0:
            return []

        actual_k = min(k, count)
        # similarity_search_with_relevance_scores: score 범위 0~1 (1=완전일치)
        results = _tag_vectorstore.similarity_search_with_relevance_scores(
            query, k=actual_k
        )

        candidates = []
        for doc, score in results:
            meta = doc.metadata
            candidates.append(
                TagCandidate(
                    tag_path=meta.get("tag_path", ""),
                    display_name=meta.get("display_name", ""),
                    description=meta.get("description", ""),
                    tag_type=meta.get("tag_type", ""),
                    score=round(score, 4),
                )
            )

        return candidates

    except Exception as e:
        print(f"[TagStore] 검색 실패: {e}")
        return []


def get_tag_count() -> int:
    """인덱싱된 태그 수 반환"""
    if _tag_vectorstore is None:
        return 0
    try:
        return _tag_vectorstore._collection.count()
    except Exception:
        return 0


def delete_tag_store() -> bool:
    """태그 컬렉션 전체 삭제 (초기화용)"""
    global _tag_vectorstore

    if _tag_vectorstore is None:
        return False

    try:
        _tag_vectorstore.delete_collection()
        _tag_vectorstore = None
        print("[TagStore] 컬렉션 삭제 완료")
        return True
    except Exception as e:
        print(f"[TagStore] 삭제 실패: {e}")
        return False
