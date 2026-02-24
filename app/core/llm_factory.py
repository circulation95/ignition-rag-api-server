from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import settings


def get_llm(temperature: float = 0) -> BaseChatModel:
    """
    LLM 프로바이더 설정에 따라 적절한 Chat 모델 인스턴스를 반환합니다.

    환경변수 또는 .env 파일에서 LLM_PROVIDER 값으로 제어합니다:
      - "openrouter" → ChatOpenAI (OpenRouter API, Qwen 2.5 72B 등 한국어 특화)
      - "openai"     → ChatOpenAI (OpenAI API 직접 호출)
      - "ollama"     → ChatOllama (로컬 모델)

    Args:
        temperature: 생성 다양성 (0 = 결정적, 1 = 창의적)

    Returns:
        BaseChatModel 인스턴스
    """
    provider = settings.llm_provider.lower()

    if provider == "openrouter":
        from langchain_openai import ChatOpenAI

        if not settings.openrouter_api_key:
            raise ValueError(
                "LLM_PROVIDER=openrouter 이지만 OPENROUTER_API_KEY가 설정되지 않았습니다.\n"
                "https://openrouter.ai/keys 에서 API 키를 발급받으세요."
            )

        return ChatOpenAI(
            model=settings.openrouter_model_name,
            temperature=temperature,
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            default_headers={
                "HTTP-Referer": "https://ignition-rag-api-server",
                "X-Title": "Ignition SCADA Agent",
            },
        )

    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        if not settings.openai_api_key:
            raise ValueError(
                "LLM_PROVIDER=openai 이지만 OPENAI_API_KEY가 설정되지 않았습니다."
            )

        return ChatOpenAI(
            model=settings.openai_model_name,
            temperature=temperature,
            api_key=settings.openai_api_key,
        )

    elif provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=settings.llm_model_name,
            temperature=temperature,
            base_url=settings.ollama_base_url,
        )

    else:
        raise ValueError(
            f"지원하지 않는 LLM_PROVIDER: '{settings.llm_provider}'. "
            "'openrouter', 'openai', 'ollama' 중 하나를 사용하세요."
        )
