import os
import sys
import shutil

import glob
from typing import List, Annotated, TypedDict
from contextlib import asynccontextmanager

# FastAPI
from fastapi import FastAPI
from pydantic import BaseModel, Field
import uvicorn

# LangChain & Models
from langchain_ollama import ChatOllama
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.documents import Document
from langgraph.graph import END, StateGraph, START

# 문서 처리 및 벡터 DB
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from dotenv import load_dotenv

# --- [0. 설정] ---
load_dotenv()

# 임베딩 모델 (Hugging Face)
EMBEDDING_MODEL_NAME = "intfloat/multilingual-e5-large"
DB_PATH = "./faiss_index"

# LLM 모델 (Ollama)
LLM_MODEL_NAME = "qwen2.5:7b"

global_retriever = None


# --- [1. LangSmith 설정] ---
def langsmith_setup(project_name="Ignition-Pro-RAG"):
    if os.environ.get("LANGCHAIN_API_KEY"):
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
        os.environ["LANGCHAIN_PROJECT"] = project_name
        print(f"[System] LangSmith 추적 활성화: {project_name}")


langsmith_setup()


# --- [2. Lifespan: DB 로드 또는 생성] ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global global_retriever
    print("\n[System] 서버 초기화 중...")

    # 임베딩 모델 로드 (CUDA 가속)
    print(f"[System] 임베딩 모델({EMBEDDING_MODEL_NAME}) 로드 중... (CUDA)")
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={"device": "cuda"},
        encode_kwargs={"normalize_embeddings": True},
    )

    # DB 존재 여부 확인
    if os.path.exists(DB_PATH):
        print("[System] 저장된 벡터 DB 발견. 로딩 중...")
        try:
            vectorstore = FAISS.load_local(
                DB_PATH, embeddings, allow_dangerous_deserialization=True
            )
            global_retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
            print("[System] DB 로딩 완료.")
        except Exception as e:
            print(f"[Error] DB 로딩 실패: {e}")
            print(" -> 기존 DB 삭제 후 재생성을 권장합니다.")

    else:
        print("[System] 저장된 DB 없음. PDF 문서 처리 시작.")

        if not os.path.exists("document"):
            os.makedirs("document")

        pdf_files = glob.glob("document/*.pdf")

        if not pdf_files:
            print("[Warning] 'document' 폴더에 PDF 파일이 없습니다.")
        else:
            all_splits = []
            for file_path in pdf_files:
                try:
                    loader = PyPDFLoader(file_path)
                    docs = loader.load()
                    text_splitter = RecursiveCharacterTextSplitter(
                        chunk_size=500, chunk_overlap=50
                    )
                    splits = text_splitter.split_documents(docs)
                    all_splits.extend(splits)
                    print(f" - {os.path.basename(file_path)} 처리 완료")
                except Exception as e:
                    print(f"[Error] 로드 실패: {file_path}")

            if all_splits:
                print(f"[System] 벡터 DB 생성 및 저장 중... ({DB_PATH})")
                vectorstore = FAISS.from_documents(
                    documents=all_splits, embedding=embeddings
                )
                vectorstore.save_local(DB_PATH)
                global_retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
                print("[System] DB 생성 및 저장 완료.")

    yield
    print("[System] 서버 종료")


app = FastAPI(title="High-Performance Local RAG", lifespan=lifespan)

# --- [3. RAG 로직] ---


class GradeDocuments(BaseModel):
    binary_score: str = Field(description="'yes' or 'no'")


class GraphState(TypedDict):
    question: str
    generation: str
    documents: List[Document]


def retrieve(state: GraphState):
    print("\n[1] 문서 검색")
    if global_retriever is None:
        return {"documents": []}

    docs = global_retriever.invoke(state["question"])
    print(f" -> {len(docs)}개 문서 검색됨")
    return {"documents": docs}


def grade_documents(state: GraphState):
    print("\n[2] 문서 평가")
    question = state["question"]
    documents = state["documents"]

    llm = ChatOllama(model=LLM_MODEL_NAME, temperature=0, num_gpu=-1)
    parser = JsonOutputParser(pydantic_object=GradeDocuments)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a grader. If the document is relevant to the question, return JSON {{'binary_score': 'yes'}}. Otherwise {{'binary_score': 'no'}}.",
            ),
            ("human", "Doc: {document}\nQuestion: {question}"),
        ]
    )

    chain = prompt | llm | parser

    filtered_docs = []
    for doc in documents:
        try:
            score = chain.invoke({"question": question, "document": doc.page_content})
            if score.get("binary_score") == "yes":
                filtered_docs.append(doc)
        except:
            continue

    print(f" -> {len(filtered_docs)}/{len(documents)}개 문서 유효함")
    return {"documents": filtered_docs}


def generate(state: GraphState):
    print("\n[3] 답변 생성")
    documents = state["documents"]
    question = state["question"]

    if not documents:
        return {"generation": "죄송합니다. 제공된 문서 내용으로는 답변할 수 없습니다."}

    llm = ChatOllama(model=LLM_MODEL_NAME, temperature=0, num_gpu=-1, num_ctx=4096)

    system_prompt = (
        "You are a Data Center Expert. "
        "Answer the user's question strictly in **Korean**, based **only** on the provided Context. "
        "If the answer is not in the context, state that you do not have the information. "
        "Do not hallucinate or make up facts."
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            # 문맥과 질문을 명확하게 분리하여 주입
            (
                "human",
                "Context:\n{context}\n\nQuestion:\n{question}\n\nAnswer (in Korean):",
            ),
        ]
    )

    chain = prompt | llm | StrOutputParser()
    result = chain.invoke({"context": documents, "question": question})
    return {"generation": result}


def build_graph():
    workflow = StateGraph(GraphState)
    workflow.add_node("retrieve", retrieve)
    workflow.add_node("grade_documents", grade_documents)
    workflow.add_node("generate", generate)
    workflow.add_edge(START, "retrieve")
    workflow.add_edge("retrieve", "grade_documents")
    workflow.add_edge("grade_documents", "generate")
    workflow.add_edge("generate", END)
    return workflow.compile()


app_graph = build_graph()


# --- [4. API] ---
class QueryRequest(BaseModel):
    question: str


@app.post("/ask")
async def ask_rag(request: QueryRequest):
    print(f"[Request] {request.question}")
    result = app_graph.invoke({"question": request.question})

    sources = list(
        set(
            [
                doc.metadata.get("source", "Unknown")
                for doc in result.get("documents", [])
            ]
        )
    )
    print(f"[Response] 답변 완료 (Sources: {len(sources)})")

    return {
        "question": request.question,
        "answer": result["generation"],
        "sources": sources,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
