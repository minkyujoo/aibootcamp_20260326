"""사업기회 수주확률: 단계 기반 + 활동 빈도·최근성·키워드 규칙."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from rag_agent.crm.models import Activity, Opportunity

_STAGE_BASE: dict[str, float] = {
    "발굴": 0.12,
    "니즈확인": 0.28,
    "제안": 0.48,
    "협상": 0.68,
    "계약": 0.88,
    "수주": 1.0,
    "실주": 0.0,
}

_REQ_KEYWORDS = ("요구사항", "RFP", "스펙", "기능", "범위", "니즈", "과제")
_CONTRACT_KEYWORDS = ("계약", "SOW", "조건", "단가", "견적", "협상", "PO")


def _naive_utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def activities_for_opportunity(
    db: Session, opp: Opportunity
) -> list[Activity]:
    from rag_agent.crm.models import Activity

    q1 = (
        db.query(Activity)
        .filter(Activity.opportunity_id == opp.id)
        .order_by(Activity.created_at.desc())
        .all()
    )
    q2 = (
        db.query(Activity)
        .filter(
            Activity.company_id == opp.company_id,
            Activity.opportunity_id.is_(None),
        )
        .order_by(Activity.created_at.desc())
        .all()
    )
    seen: set[int] = set()
    out: list[Activity] = []
    for a in q1 + q2:
        if a.id in seen:
            continue
        seen.add(a.id)
        out.append(a)
    out.sort(key=lambda x: x.created_at or _naive_utc_now(), reverse=True)
    return out


def win_probability_breakdown(opp: Opportunity, acts: list[Activity]) -> dict:
    """규칙 엔진 구성 요소(에이전트 설명·감사용)."""
    base = _STAGE_BASE.get(opp.stage, 0.2)
    if opp.stage in ("수주", "실주"):
        final = float(base)
        return {
            "stage": opp.stage,
            "base_component": round(base, 3),
            "activity_count": len(acts),
            "activity_frequency_bonus": 0.0,
            "recency_bonus": 0.0,
            "recency_tier": "—",
            "requirement_keyword_bonus": 0.0,
            "contract_keyword_bonus": 0.0,
            "sum_before_cap": final,
            "final_probability": final,
        }

    n = len(acts)
    freq_b = min(0.18, n * 0.025)
    recency_b = 0.0
    recency_tier = "없음(활동 없음)"
    now = _naive_utc_now()
    if acts:
        latest = acts[0].created_at
        if latest:
            if isinstance(latest, datetime) and latest.tzinfo:
                latest = latest.replace(tzinfo=None)
            delta = now - latest
            if delta <= timedelta(days=7):
                recency_b = 0.10
                recency_tier = "7일 이내"
            elif delta <= timedelta(days=30):
                recency_b = 0.05
                recency_tier = "30일 이내"
            else:
                recency_tier = "30일 초과"

    blob = "\n".join((a.subject or "") + "\n" + (a.body or "") for a in acts)
    req_b = 0.06 if any(k in blob for k in _REQ_KEYWORDS) else 0.0
    ctr_b = 0.08 if any(k in blob for k in _CONTRACT_KEYWORDS) else 0.0
    raw = base + freq_b + recency_b + req_b + ctr_b
    final = max(0.02, min(0.95, round(raw, 3)))
    return {
        "stage": opp.stage,
        "base_component": round(base, 3),
        "activity_count": n,
        "activity_frequency_bonus": round(freq_b, 3),
        "recency_bonus": round(recency_b, 3),
        "recency_tier": recency_tier,
        "requirement_keyword_bonus": req_b,
        "contract_keyword_bonus": ctr_b,
        "sum_before_cap": round(raw, 3),
        "final_probability": final,
    }


def compute_win_probability(opp: Opportunity, acts: list[Activity]) -> float:
    return float(win_probability_breakdown(opp, acts)["final_probability"])


def win_probability_rationale_summary(bd: dict, stored_probability: float) -> str:
    """상세 화면용: 규칙 엔진 요약을 짧은 한국어 문장으로."""
    st = str(bd.get("stage") or "")
    pct = stored_probability * 100
    if st == "수주":
        return "단계가「수주」라 규칙상 수주확률 100%로 고정됩니다."
    if st == "실주":
        return "단계가「실주」라 규칙상 수주확률 0%로 고정됩니다."
    base = float(bd.get("base_component") or 0)
    n = int(bd.get("activity_count") or 0)
    fb = float(bd.get("activity_frequency_bonus") or 0)
    rb = float(bd.get("recency_bonus") or 0)
    tier = str(bd.get("recency_tier") or "—")
    req = float(bd.get("requirement_keyword_bonus") or 0)
    ctr = float(bd.get("contract_keyword_bonus") or 0)
    raw = float(bd.get("sum_before_cap") or 0)
    parts: list[str] = [
        f"「{st}」단계 기본 약 {base * 100:.0f}%p에서 시작합니다.",
        f"이 기회에 연결·매핑된 영업활동 {n}건 반영으로 빈도 가산 약 {fb * 100:.1f}%p입니다.",
        f"최근 활동 시점은「{tier}」기준으로 최근성 가산 {rb * 100:.1f}%p입니다.",
    ]
    extras: list[str] = []
    if req > 0:
        extras.append("활동 본문의 요구·RFP·과제류 키워드 +6%p")
    if ctr > 0:
        extras.append("계약·견적·협상류 키워드 +8%p")
    if extras:
        parts.append("추가: " + " · ".join(extras) + ".")
    parts.append(
        f"위 항목을 더한 뒤(합산 약 {raw * 100:.1f}%) 시스템 상·하한을 적용해 "
        f"지금 DB 수주확률은 {pct:.1f}%입니다."
    )
    return " ".join(parts)


def recalculate_opportunity(db: Session, opp: Opportunity) -> float:
    acts = activities_for_opportunity(db, opp)
    p = compute_win_probability(opp, acts)
    opp.win_probability = p
    db.add(opp)
    db.commit()
    db.refresh(opp)
    return p
