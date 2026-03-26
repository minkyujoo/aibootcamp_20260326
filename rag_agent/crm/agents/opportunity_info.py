"""사업기회 정보 문의 Agent."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rag_agent.config import Settings
from rag_agent.crm.agents.llm import llm_reply
from rag_agent.crm.agents.types import CrmAgentPayload, CrmAgentResult
from rag_agent.crm.probability import activities_for_opportunity

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


async def run(db: Session, settings: Settings, p: CrmAgentPayload) -> CrmAgentResult:
    from rag_agent.crm.models import Company, Opportunity

    o = db.get(Opportunity, p.opportunity_id)
    if not o:
        return CrmAgentResult("사업기회를 찾을 수 없습니다.", "", [])
    company = db.get(Company, o.company_id)
    acts = activities_for_opportunity(db, o)
    ids = [a.id for a in acts[:40]]

    cn = company.name if company else "-"
    lines = [
        f"[사업기회] id={o.id} 이름={o.name}",
        f"고객사 id={o.company_id} ({cn}) 유형={o.project_type} 단계={o.stage}",
        f"수주확률(저장값)={o.win_probability:.1%} 담당 영업 id={o.sales_rep_id}",
        "[관련 영업활동]",
    ]
    for a in acts[:20]:
        t = a.created_at.isoformat() if a.created_at else ""
        lines.append(
            f"  id={a.id} {a.kind} {t} | {a.subject}\n    본문일부: {(a.body or '')[:400]}"
        )
    ctx = "\n".join(lines)

    sys_p = (
        "당신은 CRM의 '사업기회 정보' 전담 에이전트입니다. "
        "[사업기회 데이터]만 근거로 한국어로 답합니다."
    )
    user = f"[사업기회 데이터]\n{ctx}\n\n[사용자 질문]\n{p.message or '이 기회를 요약해 주세요.'}"
    out = await llm_reply(settings, sys_p, user)
    if out is None:
        out = f"### 사업기회 정보 (LLM 미설정)\n\n{ctx}"
    return CrmAgentResult(out, ctx[:2000], ids)
