from __future__ import annotations

import logging

from rag_agent.config import Settings
from rag_agent.llm_client import chat_completions_create, llm_is_configured

_log = logging.getLogger(__name__)


async def llm_reply(
    settings: Settings,
    system: str,
    user: str,
    *,
    max_tokens: int = 1800,
) -> str | None:
    """LLM 미구성이면 None. API 오류 시 로그 후 None (호출부가 규칙 기반 폴백 가능)."""
    if not llm_is_configured(settings):
        return None
    try:
        resp = await chat_completions_create(
            settings,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user[:14000]},
            ],
            max_tokens=max_tokens,
            stream=False,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        _log.exception("llm_reply: chat.completions 호출 실패")
        return None
