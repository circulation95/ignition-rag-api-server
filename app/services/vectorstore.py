from __future__ import annotations

import os

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_core.vectorstores import VectorStoreRetriever

from app.core.config import settings


_retriever: VectorStoreRetriever | None = None


def init_retriever() -> bool:
    global _retriever
    embeddings = HuggingFaceEmbeddings(
        model_name=settings.embedding_model_name,
        model_kwargs={"device": settings.embedding_device},
        encode_kwargs={"normalize_embeddings": settings.embedding_normalize},
    )

    index_file = os.path.join(settings.vectorstore_path, "index.faiss")
    store_file = os.path.join(settings.vectorstore_path, "index.pkl")

    if os.path.exists(settings.vectorstore_path) and os.path.exists(index_file):
        vectorstore = FAISS.load_local(
            settings.vectorstore_path,
            embeddings,
            allow_dangerous_deserialization=True,
        )
        _retriever = vectorstore.as_retriever(search_kwargs={"k": settings.vectorstore_k})
        return True

    # Auto-create an empty FAISS index when the path is missing.
    try:
        os.makedirs(settings.vectorstore_path, exist_ok=True)
        embedding_dim = len(embeddings.embed_query(" "))
        import faiss

        index = faiss.IndexFlatL2(embedding_dim)
        docstore = InMemoryDocstore({})
        index_to_docstore_id = {}
        vectorstore = FAISS(
            embedding_function=embeddings,
            index=index,
            docstore=docstore,
            index_to_docstore_id=index_to_docstore_id,
        )
        vectorstore.save_local(settings.vectorstore_path)
        _retriever = None
        return False
    except Exception:
        _retriever = None
        return False


def get_retriever() -> VectorStoreRetriever | None:
    return _retriever
