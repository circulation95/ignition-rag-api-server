"""Chroma 벡터스토어 서비스 - 임베딩 provider 전환 지원 (OpenAI / HuggingFace)"""

from __future__ import annotations

import os
from typing import Optional

from langchain_chroma import Chroma
from langchain_core.vectorstores import VectorStoreRetriever

from app.core.config import settings


_retriever: VectorStoreRetriever | None = None
_vectorstore: Chroma | None = None


def get_embeddings():
    """
    임베딩 모델 인스턴스 생성.

    EMBEDDING_PROVIDER 설정에 따라:
      - "openai"       → OpenAIEmbeddings (text-embedding-3-large, 한국어 최적)
      - "huggingface"  → HuggingFaceEmbeddings (로컬, GPU 가능)
    """
    provider = settings.embedding_provider.lower()

    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        if not settings.openai_api_key:
            raise ValueError(
                "EMBEDDING_PROVIDER=openai 이지만 OPENAI_API_KEY가 설정되지 않았습니다."
            )

        return OpenAIEmbeddings(
            model=settings.embedding_model_name,
            api_key=settings.openai_api_key,
        )

    elif provider == "huggingface":
        from langchain_huggingface import HuggingFaceEmbeddings

        return HuggingFaceEmbeddings(
            model_name=settings.embedding_hf_model_name,
            model_kwargs={"device": settings.embedding_device},
            encode_kwargs={"normalize_embeddings": settings.embedding_normalize},
        )

    else:
        raise ValueError(
            f"지원하지 않는 EMBEDDING_PROVIDER: '{settings.embedding_provider}'. "
            "'openai' 또는 'huggingface'를 사용하세요."
        )


def init_retriever() -> bool:
    """
    Chroma 벡터스토어 초기화 및 retriever 설정.

    Returns:
        True: 기존 데이터가 있어 retriever 활성화됨
        False: 빈 컬렉션이거나 초기화 실패
    """
    global _retriever, _vectorstore

    embeddings = get_embeddings()

    # Chroma persist 디렉토리 생성
    os.makedirs(settings.vectorstore_path, exist_ok=True)

    try:
        # Chroma 벡터스토어 초기화 (PersistentClient 자동 사용)
        _vectorstore = Chroma(
            collection_name=settings.chroma_collection_name,
            embedding_function=embeddings,
            persist_directory=settings.vectorstore_path,
        )

        # 컬렉션에 문서가 있는지 확인
        collection_count = _vectorstore._collection.count()

        if collection_count > 0:
            _retriever = _vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={"k": settings.vectorstore_k},
            )
            print(f"[Vectorstore] Chroma 로드 완료: {collection_count}개 문서 "
                  f"(임베딩: {settings.embedding_provider}/{settings.embedding_model_name})")
            return True
        else:
            print("[Vectorstore] Chroma 컬렉션이 비어있습니다.")
            _retriever = None
            return False

    except Exception as e:
        print(f"[Vectorstore] Chroma 초기화 실패: {e}")
        _retriever = None
        _vectorstore = None
        return False


def get_retriever() -> VectorStoreRetriever | None:
    """현재 retriever 인스턴스 반환"""
    return _retriever


def get_vectorstore() -> Optional[Chroma]:
    """현재 vectorstore 인스턴스 반환 (문서 추가용)"""
    return _vectorstore


def add_documents(documents: list, ids: Optional[list] = None) -> bool:
    """
    벡터스토어에 문서 추가.

    Args:
        documents: LangChain Document 객체 리스트
        ids: 문서 ID 리스트 (선택)

    Returns:
        성공 여부
    """
    global _retriever

    if _vectorstore is None:
        print("[Vectorstore] 벡터스토어가 초기화되지 않았습니다.")
        return False

    try:
        if ids:
            _vectorstore.add_documents(documents, ids=ids)
        else:
            _vectorstore.add_documents(documents)

        # retriever 업데이트
        _retriever = _vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": settings.vectorstore_k},
        )

        print(f"[Vectorstore] {len(documents)}개 문서 추가 완료")
        return True
    except Exception as e:
        print(f"[Vectorstore] 문서 추가 실패: {e}")
        return False


def search_with_filter(
    query: str,
    k: int = 5,
    filter_dict: Optional[dict] = None,
) -> list:
    """
    메타데이터 필터링이 포함된 검색.

    Args:
        query: 검색 쿼리
        k: 반환할 문서 수
        filter_dict: 메타데이터 필터 (예: {"source": "manual"})

    Returns:
        Document 리스트
    """
    if _vectorstore is None:
        return []

    try:
        if filter_dict:
            return _vectorstore.similarity_search(
                query, k=k, filter=filter_dict
            )
        else:
            return _vectorstore.similarity_search(query, k=k)
    except Exception as e:
        print(f"[Vectorstore] 검색 실패: {e}")
        return []


def delete_collection() -> bool:
    """컬렉션 삭제 (초기화용)"""
    global _retriever, _vectorstore

    if _vectorstore is None:
        return False

    try:
        _vectorstore.delete_collection()
        _retriever = None
        print("[Vectorstore] 컬렉션 삭제 완료")
        return True
    except Exception as e:
        print(f"[Vectorstore] 컬렉션 삭제 실패: {e}")
        return False
