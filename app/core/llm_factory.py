from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import settings


def get_llm(temperature: float = 0) -> BaseChatModel:
    """
    LLM 프로바이더 설정에 따라 ChatOllama 또는 ChatOpenAI 인스턴스를 반환합니다.

    환경변수 또는 .env 파일에서 LLM_PROVIDER 값으로 제어합니다:
      - "ollama"  → ChatOllama (기본값, 로컬 모델)
      - "openai"  → ChatOpenAI (OpenAI API)

    Args:
        temperature: 생성 다양성 (0 = 결정적, 1 = 창의적)

    Returns:
        BaseChatModel 인스턴스
    """
    provider = settings.llm_provider.lower()

    if provider == "openai":
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
            "'ollama' 또는 'openai'를 사용하세요."
        )
