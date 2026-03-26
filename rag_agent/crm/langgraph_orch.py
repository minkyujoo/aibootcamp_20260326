"""CRM 오케스트레이션: RAG 검색 → 라우팅·에이전트 실행.

LangGraph 2노드(retrieve → execute)와 동일한 **논리 순서**를 비동기 순차 호출로 수행합니다.
(그래프 상태에 비직렬화 객체를 넣지 않아 환경별 Internal Server Error를 피합니다.)
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from rag_agent.config import Settings
from rag_agent.crm.agents.types import CrmAgentResult
from rag_agent.crm.orchestrate import (
    _orchestrate_with_rag_block,
    _rag_context,
    normalize_crm_user_message,
)


async def run_crm_orch_graph(
    db: Session,
    settings: Settings,
    *,
    message: str,
    current_menu: str | None = None,
    context_company_id: int | None = None,
    context_opportunity_id: int | None = None,
    context_sales_rep_id: int | None = None,
    use_rag: bool = True,
) -> CrmAgentResult:
    message = normalize_crm_user_message(message)
    if use_rag:
        rag_snippets, rag_block = await _rag_context(message, settings)
    else:
        rag_snippets, rag_block = [], ""
    return await _orchestrate_with_rag_block(
        db,
        settings,
        message=message,
        current_menu=current_menu,
        context_company_id=context_company_id,
        context_opportunity_id=context_opportunity_id,
        context_sales_rep_id=context_sales_rep_id,
        rag_snippets=rag_snippets,
        rag_block=rag_block,
    )
