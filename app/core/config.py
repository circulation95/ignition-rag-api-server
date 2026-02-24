from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Ignition Agent"
    env: str = "dev"
    debug: bool = False

    # ── 임베딩 설정 ──────────────────────────────────────────────
    # provider: "openai" | "huggingface"
    embedding_provider: str = "openai"

    # OpenAI 임베딩 (권장: 한국어 성능 우수, 가성비 최적)
    embedding_model_name: str = "text-embedding-3-large"

    # HuggingFace 임베딩 (로컬 폴백용)
    embedding_hf_model_name: str = "intfloat/multilingual-e5-large"
    embedding_device: str = "cpu"
    embedding_normalize: bool = True

    # ── Chroma 벡터스토어 설정 ────────────────────────────────────
    vectorstore_path: str = "./chroma_db"
    vectorstore_k: int = 5
    chroma_collection_name: str = "ignition_docs"

    # ── LLM Provider 설정 ─────────────────────────────────────────
    # provider: "ollama" | "openai" | "openrouter"
    llm_provider: str = "openrouter"

    # Ollama 설정
    llm_model_name: str = "llama3.1:latest"
    ollama_base_url: str = "http://localhost:11434"

    # OpenAI 설정
    openai_api_key: str = ""
    openai_model_name: str = "gpt-4o-mini"

    # OpenRouter 설정 (한국어 특화: Qwen 2.5 72B)
    openrouter_api_key: str = ""
    openrouter_model_name: str = "qwen/qwen-2.5-72b-instruct"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # ── OPC UA ───────────────────────────────────────────────────
    opc_endpoint: str = "opc.tcp://localhost:62541"

    # ── SQL ──────────────────────────────────────────────────────
    sql_host: str = "127.0.0.1"
    sql_port: int = 3306
    sql_user: str = "ignition"
    sql_password: str = "password"
    sql_db: str = "ignition"

    # ── LangSmith 추적 설정 ───────────────────────────────────────
    langsmith_tracing: bool = False
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_api_key: str = ""
    langsmith_project: str = "default"


settings = Settings()
