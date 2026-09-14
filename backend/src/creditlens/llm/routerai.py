from __future__ import annotations

from typing import Any

from creditlens.config import get_settings


def llm_available() -> bool:
    return get_settings().llm_configured


def chat_model() -> Any:
    settings = get_settings()
    if not settings.llm_configured:
        return None
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=0.1,
        max_tokens=settings.max_output_tokens,
        timeout=settings.agent_timeout_sec,
    )


def embeddings_model() -> Any:
    settings = get_settings()
    if not settings.llm_configured:
        return None
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        model=settings.llm_embedding_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        check_embedding_ctx_length=False,
        model_kwargs={"encoding_format": "float"},
    )
