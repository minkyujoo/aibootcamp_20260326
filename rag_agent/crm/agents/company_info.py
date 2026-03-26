"""고객사 정보 문의 Agent."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rag_agent.config import Settings
from rag_agent.crm.agents.llm import llm_reply
from rag_agent.crm.agents.types import CrmAgentPayload, CrmAgentResult

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


async def run(db: Session, settings: Settings, p: CrmAgentPayload) -> CrmAgentResult:
    from rag_agent.crm.models import Activity, Company, Opportunity

    c = db.get(Company, p.company_id)
    if not c:
        return CrmAgentResult("고객사를 찾을 수 없습니다.", "", [])

    opps = (
        db.query(Opportunity)
        .filter(Opportunity.company_id == c.id)
        .order_by(Opportunity.id)
        .all()
    )
    acts = (
        db.query(Activity)
        .filter(Activity.company_id == c.id)
        .order_by(Activity.created_at.desc())
        .limit(30)
        .all()
    )
    ids = [a.id for a in acts]

    lines = [
        f"[고객사] id={c.id} 이름={c.name}",
        f"사업자번호={c.biz_reg_no or '-'} 주소={c.address or '-'} 업종={c.industry or '-'}",
        f"데이터출처={c.data_source_note}",
        f"담당 영업 id={c.sales_rep_id}",
    ]
    if c.dart_profile:
        lines.append(f"DART·공시 기반 개요={c.dart_profile}")
    lines.append("[소속 사업기회 요약]")
    for o in opps:
        lines.append(
            f"  - id={o.id} {o.name} | 유형={o.project_type} 단계={o.stage} "
            f"수주확률={o.win_probability:.1%} 담당={o.sales_rep_id}"
        )
    lines.append("[최근 영업활동]")
    for a in acts[:15]:
        t = a.created_at.isoformat() if a.created_at else ""
        lines.append(f"  id={a.id} {a.kind} {t} | {a.subject}")
    ctx = "\n".join(lines)

    sys_p = (
        "당신은 CRM의 '고객사 정보' 전담 에이전트입니다. "
        "제공된 [고객사 데이터]만 근거로 한국어로 답합니다. "
        "추측하지 말고 없으면 '데이터에 없음'이라고 합니다."
    )
    user = f"[고객사 데이터]\n{ctx}\n\n[사용자 질문]\n{p.message or '이 고객사를 요약해 주세요.'}"
    out = await llm_reply(settings, sys_p, user)
    if out is None:
        out = f"### 고객사 정보 (LLM 미설정)\n\n{ctx}"
    return CrmAgentResult(out, ctx[:2000], ids)
