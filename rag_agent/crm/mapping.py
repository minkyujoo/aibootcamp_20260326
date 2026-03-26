"""활동 본문에서 고객사·사업기회 자동 매핑 제안 (키워드·이름 매칭)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from rag_agent.crm.models import Company, Opportunity


@dataclass
class Suggestion:
    company_id: int | None
    opportunity_id: int | None
    company_score: float
    opportunity_score: float
    reason: str


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def suggest_mapping(db: Session, text: str) -> Suggestion:
    from rag_agent.crm.models import Company, Opportunity

    t = _norm(text)
    best_c: tuple[int | None, float, str] = (None, 0.0, "")
    for c in db.query(Company).order_by(Company.id).all():
        name = _norm(c.name)
        if not name:
            continue
        score = 0.0
        if name in t:
            score = 0.95
        elif any(part in t for part in name.split() if len(part) >= 2):
            score = 0.55
        if score > best_c[1]:
            best_c = (c.id, score, f"회사명 매칭: {c.name}")

    best_o: tuple[int | None, float, str] = (None, 0.0, "")
    for o in (
        db.query(Opportunity)
        .join(Company, Opportunity.company_id == Company.id)
        .order_by(Opportunity.id)
        .all()
    ):
        on = _norm(o.name)
        pt = _norm(o.project_type or "")
        score = 0.0
        reason = ""
        if on and on in t:
            score = max(score, 0.9)
            reason = f"기회명 매칭: {o.name}"
        if pt and pt in t:
            score = max(score, 0.65)
            reason = reason or f"유형 키워드: {o.project_type}"
        if score > best_o[1]:
            best_o = (o.id, score, reason)

    cid, cs, cr = best_c
    oid, os_, or_ = best_o
    if oid is not None:
        opp = db.get(Opportunity, oid)
        if opp and cid is not None and opp.company_id != cid:
            if cs >= os_:
                oid = None
                os_ = 0.0
                or_ = ""
            else:
                cid = opp.company_id
                cs = min(cs + 0.2, 1.0)
                cr = cr or f"기회 소속 회사 ID {cid}"

    parts = [p for p in (cr, or_) if p]
    return Suggestion(
        company_id=cid,
        opportunity_id=oid,
        company_score=cs,
        opportunity_score=os_,
        reason="; ".join(parts) if parts else "명시적 매칭 없음",
    )
