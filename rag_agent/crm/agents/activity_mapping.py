"""영업활동 → 고객사·사업기회 매핑 Agent (규칙 + LLM 설명)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rag_agent.config import Settings
from rag_agent.crm.agents.llm import llm_reply
from rag_agent.crm.agents.types import CrmAgentPayload, CrmAgentResult
from rag_agent.crm.mapping import suggest_mapping

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


async def run(db: Session, settings: Settings, p: CrmAgentPayload) -> CrmAgentResult:
    from rag_agent.crm.models import Company, Opportunity

    text = (p.activity_text or p.message or "").strip()
    if not text:
        return CrmAgentResult(
            "매핑할 활동 본문을 message 또는 activity_text로 보내 주세요.",
            "",
            [],
        )

    sug = suggest_mapping(db, text)
    co = db.get(Company, sug.company_id) if sug.company_id else None
    op = db.get(Opportunity, sug.opportunity_id) if sug.opportunity_id else None

    structured = {
        "suggested_company_id": sug.company_id,
        "suggested_opportunity_id": sug.opportunity_id,
        "company_score": sug.company_score,
        "opportunity_score": sug.opportunity_score,
        "rule_reason": sug.reason,
    }

    ctx = (
        f"[활동 초안]\n{text[:4000]}\n\n"
        f"[규칙 엔진 제안]\n"
        f"company_id={sug.company_id} ({co.name if co else '—'}) score={sug.company_score:.2f}\n"
        f"opportunity_id={sug.opportunity_id} ({op.name if op else '—'}) score={sug.opportunity_score:.2f}\n"
        f"사유: {sug.reason}"
    )

    sys_p = (
        "당신은 CRM의 '영업활동 매핑' 전담 에이전트입니다. "
        "규칙 엔진 결과를 검토하고, 본문 근거를 인용해 한국어로 설명합니다. "
        "불확실하면 사용자에게 확인 질문을 제시합니다."
    )
    user = f"{ctx}\n\n[사용자 요청]\n{p.message if p.activity_text else '이 매핑이 적절한지 설명해 주세요.'}"
    if p.activity_text and p.message.strip():
        user = f"{ctx}\n\n[추가 지시]\n{p.message}"

    out = await llm_reply(settings, sys_p, user)
    if out is None:
        out = f"### 활동 매핑 (LLM 미설정)\n\n{ctx}"
    return CrmAgentResult(out, ctx[:2000], [], structured)
