"""채팅용 LLM 클라이언트 — Azure OpenAI(AOAI) 우선, OpenAI 공식 API 폴백."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openai import AsyncAzureOpenAI, AsyncOpenAI

    from rag_agent.config import Settings


def llm_is_configured(settings: Settings) -> bool:
    if settings.use_azure_openai():
        return True
    return bool(settings.openai_api_key)


def get_async_chat_client(settings: Settings) -> AsyncAzureOpenAI | AsyncOpenAI:
    if settings.use_azure_openai():
        from openai import AsyncAzureOpenAI

        ep = (settings.aoai_endpoint or "").strip().rstrip("/")
        return AsyncAzureOpenAI(
            azure_endpoint=ep,
            api_key=settings.aoai_api_key,
            api_version=settings.aoai_api_version,
        )
    from openai import AsyncOpenAI

    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )


def chat_deployment_name(settings: Settings) -> str:
    """채팅 API `model` 인자에 넣을 배포명/모델명."""
    if settings.use_azure_openai():
        return settings.resolved_aoai_chat_deployment()
    return settings.openai_model


async def chat_completions_create(
    settings: Settings,
    *,
    messages: list[dict[str, Any]],
    max_tokens: int,
    stream: bool = False,
    model: str | None = None,
) -> Any:
    client = get_async_chat_client(settings)
    name = model or chat_deployment_name(settings)
    return await client.chat.completions.create(
        model=name,
        messages=messages,
        max_tokens=max_tokens,
        stream=stream,
    )
