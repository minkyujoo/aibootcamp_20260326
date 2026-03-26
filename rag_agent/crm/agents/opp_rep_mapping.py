"""사업기회·영업담당 매핑 Agent (일관성 점검·제안)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rag_agent.config import Settings
from rag_agent.crm.agents.llm import llm_reply
from rag_agent.crm.agents.types import CrmAgentPayload, CrmAgentResult

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


async def run(db: Session, settings: Settings, p: CrmAgentPayload) -> CrmAgentResult:
    from rag_agent.crm.models import Company, Opportunity, SalesRep

    o = db.get(Opportunity, p.opportunity_id)
    if not o:
        return CrmAgentResult("사업기회를 찾을 수 없습니다.", "", [])
    company = db.get(Company, o.company_id)

    reps = db.query(SalesRep).order_by(SalesRep.id).all()
    rep_lines = []
    for r in reps:
        n_co = db.query(Company).filter(Company.sales_rep_id == r.id).count()
        n_op = db.query(Opportunity).filter(Opportunity.sales_rep_id == r.id).count()
        rep_lines.append(f"  id={r.id} {r.name} | 담당 고객사 {n_co}건, 사업기회 {n_op}건")

    co_rep = company.sales_rep_id if company else None
    structured = {
        "opportunity_sales_rep_id": o.sales_rep_id,
        "company_sales_rep_id": co_rep,
        "aligned": o.sales_rep_id == co_rep
        if (o.sales_rep_id is not None and co_rep is not None)
        else None,
    }

    lines = [
        f"[대상 사업기회] id={o.id} {o.name} | 현재 담당 영업 id={o.sales_rep_id}",
        f"[고객사] id={company.id if company else '-'} "
        f"{company.name if company else '-'} | 고객사 담당 영업 id={co_rep}",
        "[영업담당 후보(전원) 및 부하]",
        *rep_lines,
    ]
    ctx = "\n".join(lines)

    sys_p = (
        "당신은 CRM의 '사업기회·영업담당 매핑' 전담 에이전트입니다. "
        "고객사 담당과 사업기회 담당의 일관성, 업무량 균형을 검토하고 "
        "사용자 질문에 맞게 추천 담당자 id와 근거를 한국어로 제시합니다. "
        "확정이 아닌 제안임을 명시합니다."
    )
    user = f"{ctx}\n\n[사용자 요청]\n{p.message or '담당자 매핑을 점검하고 개선안을 제안해 주세요.'}"
    out = await llm_reply(settings, sys_p, user)
    if out is None:
        hint = ""
        if structured["aligned"] is False:
            hint = "\n\n※ 고객사 담당과 사업기회 담당이 다릅니다."
        out = f"### 매핑 점검 (LLM 미설정)\n\n{ctx}{hint}"
    return CrmAgentResult(out, ctx[:2000], [], structured)
