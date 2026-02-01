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

    embedding_model_name: str = "intfloat/multilingual-e5-large"
    embedding_device: str = "cuda"
    embedding_normalize: bool = True
    vectorstore_path: str = "./faiss_index"
    vectorstore_k: int = 5

    llm_model_name: str = "qwen3:8b"

    opc_endpoint: str = "opc.tcp://localhost:62541"

    sql_host: str = "127.0.0.1"
    sql_port: int = 3306
    sql_user: str = "ignition"
    sql_password: str = "password"
    sql_db: str = "ignition"


settings = Settings()
