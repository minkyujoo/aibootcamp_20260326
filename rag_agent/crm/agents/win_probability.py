"""사업기회 수주확률 계산·설명 Agent."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rag_agent.config import Settings
from rag_agent.crm.agents.llm import llm_reply
from rag_agent.crm.agents.types import CrmAgentPayload, CrmAgentResult
from rag_agent.crm.probability import activities_for_opportunity, win_probability_breakdown

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


async def run(db: Session, settings: Settings, p: CrmAgentPayload) -> CrmAgentResult:
    from rag_agent.crm.models import Opportunity

    o = db.get(Opportunity, p.opportunity_id)
    if not o:
        return CrmAgentResult("사업기회를 찾을 수 없습니다.", "", [])

    acts = activities_for_opportunity(db, o)
    bd = win_probability_breakdown(o, acts)
    ctx = (
        f"[규칙 기반 수주확률 분해]\n"
        f"사업기회 id={o.id} {o.name} 단계={bd['stage']}\n"
        f"- 단계 기반 점수: {bd['base_component']}\n"
        f"- 활동 건수: {bd['activity_count']} (빈도 보너스 {bd['activity_frequency_bonus']})\n"
        f"- 최근성: {bd['recency_tier']} (보너스 {bd['recency_bonus']})\n"
        f"- 요구사항 키워드 보너스: {bd['requirement_keyword_bonus']}\n"
        f"- 계약/협상 키워드 보너스: {bd['contract_keyword_bonus']}\n"
        f"- 합산(캡 전): {bd['sum_before_cap']} → 최종 확률: {bd['final_probability']}\n"
        f"(DB 저장값 win_probability={o.win_probability})"
    )

    sys_p = (
        "당신은 CRM의 '수주확률' 전담 에이전트입니다. "
        "제공된 [규칙 분해]를 바탕으로 영업 담당자가 이해하기 쉽게 한국어로 설명합니다. "
        "수치는 반드시 제공된 분해와 일치시킵니다."
    )
    user = f"{ctx}\n\n[사용자 질문]\n{p.message or '이 수치가 왜 이렇게 나왔는지 설명해 주세요.'}"
    out = await llm_reply(settings, sys_p, user)
    if out is None:
        out = f"### 수주확률 (LLM 미설정)\n\n{ctx}"
    return CrmAgentResult(out, ctx[:2000], [a.id for a in acts[:40]], bd)
