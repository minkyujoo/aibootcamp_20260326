"""영업 활동 추천 Agent (다음 액션·미팅·메일 아이디어)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import or_

from rag_agent.config import Settings
from rag_agent.crm.agents.llm import llm_reply
from rag_agent.crm.agents.types import CrmAgentPayload, CrmAgentResult
from rag_agent.crm.probability import activities_for_opportunity
from rag_agent.crm.stage_guides import STAGE_GUIDE

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _rep_top_opportunities_markdown(
    db: Session, opps: list, heading: str
) -> str:
    """수주확률 우선 사업기회 요약 표."""
    from rag_agent.crm.models import Company, Opportunity

    if not opps:
        return f"_{heading}: 해당 없음._"

    co_ids = {o.company_id for o in opps}
    cos = {c.id: c for c in db.query(Company).filter(Company.id.in_(co_ids)).all()}
    lines = [
        f"### {heading}",
        "",
        "| 고객사 | 사업기회 | 단계 | 수주확률 | id |",
        "| --- | --- | --- | --- | --- |",
    ]
    for o in opps:
        assert isinstance(o, Opportunity)
        co = cos.get(o.company_id)
        cn = (co.name if co else f"id={o.company_id}").replace("|", "\\|")
        on = (o.name or "").replace("|", "\\|")
        lines.append(
            f"| {cn} | {on} | {o.stage} | {o.win_probability:.0%} | {o.id} |"
        )
    return "\n".join(lines)


def _rep_action_items_markdown_table(db: Session, items: list) -> str:
    """담당자 포트폴리오 Action item을 고객사·사업기회 단위로 표시."""
    from rag_agent.crm.models import Company, Opportunity

    if not items:
        return "_미완료(pending/in_progress) Action item이 없습니다._"

    co_ids = {i.company_id for i in items}
    opp_ids = {i.opportunity_id for i in items if i.opportunity_id is not None}
    cos = {
        c.id: c
        for c in db.query(Company).filter(Company.id.in_(co_ids)).all()
    }
    opps: dict[int, Opportunity] = {}
    if opp_ids:
        opps = {
            o.id: o
            for o in db.query(Opportunity).filter(Opportunity.id.in_(opp_ids)).all()
        }

    lines = [
        "### 이 담당자 관련 Action item 목록 (고객사 → 사업기회)",
        "",
        "| 고객사 | 사업기회 | Action item | 상태 |",
        "| --- | --- | --- | --- |",
    ]
    for it in items:
        co = cos.get(it.company_id)
        cname = co.name if co else f"(id={it.company_id})"
        if it.opportunity_id is not None:
            o = opps.get(it.opportunity_id)
            oname = o.name if o else f"(id={it.opportunity_id})"
        else:
            oname = "—"
        title = (it.title or "").replace("|", "\\|")
        cname_esc = cname.replace("|", "\\|")
        oname_esc = oname.replace("|", "\\|")
        lines.append(f"| {cname_esc} | {oname_esc} | {title} | {it.status} |")
    return "\n".join(lines)


async def _run_for_sales_rep(
    db: Session, settings: Settings, p: CrmAgentPayload
) -> CrmAgentResult:
    from rag_agent.crm.models import ActionItem, Activity, Company, Opportunity, SalesRep

    rid = p.sales_rep_id
    assert rid is not None
    rep = db.get(SalesRep, rid)
    if not rep:
        return CrmAgentResult("영업 담당자를 찾을 수 없습니다.", "", [])

    cos = (
        db.query(Company).filter(Company.sales_rep_id == rid).order_by(Company.id).all()
    )
    opps_assigned = (
        db.query(Opportunity)
        .filter(Opportunity.sales_rep_id == rid)
        .order_by(Opportunity.id)
        .limit(100)
        .all()
    )
    cid_set = {c.id for c in cos}
    for o in opps_assigned:
        cid_set.add(o.company_id)
    cids_list = sorted(cid_set)

    if not cids_list:
        return CrmAgentResult(
            "이 담당자에게 배정된 고객사·사업기회가 없어 추천할 포트폴리오 맥락이 없습니다.",
            f"[영업담당] id={rep.id} {rep.name}",
            [],
            {"sales_rep_id": rid, "portfolio_companies": 0, "portfolio_opportunities": 0},
        )

    # 담당 기회: 본인 배정 기회 ∪ 담당 고객사 소속 기회 (수주확률 상위 3~5개 선별용)
    portfolio_opps = (
        db.query(Opportunity)
        .filter(
            or_(
                Opportunity.sales_rep_id == rid,
                Opportunity.company_id.in_(cids_list),
            )
        )
        .all()
    )
    seen: dict[int, Opportunity] = {}
    for o in portfolio_opps:
        seen[o.id] = o
    merged_opps = list(seen.values())
    merged_opps.sort(key=lambda x: (-float(x.win_probability), -x.id))
    # 수주확률 상위 최대 5개(포트폴리오가 3~5건 이상이면 3~5개가 자연스럽게 포함)
    top_focus = merged_opps[: min(5, len(merged_opps))]
    focus_opp_ids = {o.id for o in top_focus}
    focus_co_ids = {o.company_id for o in top_focus}

    items = (
        db.query(ActionItem)
        .filter(
            ActionItem.company_id.in_(cids_list),
            ActionItem.status.in_(("pending", "in_progress")),
        )
        .order_by(ActionItem.company_id, ActionItem.sort_order, ActionItem.id)
        .limit(80)
        .all()
    )

    def _item_priority(it: ActionItem) -> tuple[int, int, int]:
        if it.opportunity_id is not None and it.opportunity_id in focus_opp_ids:
            return (0, it.sort_order, it.id)
        if it.company_id in focus_co_ids:
            return (1, it.sort_order, it.id)
        return (2, it.sort_order, it.id)

    items_ordered = sorted(items, key=_item_priority)

    acts = (
        db.query(Activity)
        .filter(Activity.sales_rep_id == rid)
        .order_by(Activity.created_at.desc())
        .limit(25)
        .all()
    )
    ids = [a.id for a in acts]

    lines = [
        f"[영업담당] id={rep.id} 이름={rep.name}",
        f"[담당 고객사] {len(cos)}곳 · [포트폴리오 사업기회(중복 제거)] {len(merged_opps)}건",
        "[수주 가능성이 높은 우선 사업기회 — Action item 추천 시 최우선으로 참고]",
    ]
    for o in top_focus:
        lines.append(
            f"  ★ id={o.id} {o.name} | 단계={o.stage} 수주확률={o.win_probability:.0%} "
            f"company_id={o.company_id}"
        )
    if len(merged_opps) > len(top_focus):
        lines.append("[그 외 포트폴리오 사업기회 일부]")
        rest = [x for x in merged_opps if x.id not in focus_opp_ids][:25]
        for o in rest:
            lines.append(
                f"  - id={o.id} {o.name} | 단계={o.stage} 수주확률={o.win_probability:.0%} "
                f"company_id={o.company_id}"
            )
    lines.append("[담당 고객사 일부]")
    for c in cos[:15]:
        lines.append(f"  - id={c.id} {c.name}")
    lines.append("[미완료 Action item — ★ 우선 기회 관련이 앞쪽]")
    if not items_ordered:
        lines.append("  (등록된 미완료 Action item 없음)")
    for it in items_ordered[:50]:
        oid = it.opportunity_id if it.opportunity_id is not None else "—"
        mark = "★" if it.opportunity_id in focus_opp_ids or it.company_id in focus_co_ids else "·"
        hint = (it.hint or "")[:280]
        lines.append(
            f"  {mark} id={it.id} co={it.company_id} opp={oid} [{it.status}] {it.title}\n"
            f"    hint: {hint}"
        )
    lines.append("[담당자 소속 최근 활동]")
    for a in acts[:12]:
        t = a.created_at.isoformat() if a.created_at else ""
        lines.append(f"  id={a.id} {a.kind} {t} | {a.subject}")

    ctx = "\n".join(lines)
    guide = STAGE_GUIDE.get("발굴", STAGE_GUIDE["발굴"])
    ctx = f"{ctx}\n\n[단계 가이드 참고(포트폴리오 공통)]\n{guide[:1200]}"

    sys_p = (
        "당신은 CRM의 '영업 활동 추천' 전담 에이전트입니다. "
        "담당자에게 company_id/opportunity_id가 없을 때는, 시스템이 수주확률 기준으로 고른 "
        "「우선 사업기회」3~5개를 중심으로 어떤 Action item을 먼저 처리할지와 그 외 다음 행동을 제안합니다. "
        "앞부분 마크다운 표(우선 기회·Action item)는 유지하고, 표를 베껴 쓰지 말고 "
        "우선순위·근거·구체적 다음 행동(미팅·메일·내부 정합)을 한국어 번호 목록으로 짧게 제시합니다."
    )
    user = f"{ctx}\n\n[사용자 요청]\n{p.message or '이 담당 관점에서 다음에 할 일을 추천해 주세요.'}"
    top_md = _rep_top_opportunities_markdown(
        db, top_focus, "수주 가능성이 높은 우선 사업기회 (추천 초점)"
    )
    table_md = _rep_action_items_markdown_table(db, items_ordered)
    out = await llm_reply(settings, sys_p, user)
    if out is None:
        out = (
            f"{top_md}\n\n{table_md}\n\n---\n\n### 우선순위 제안 (LLM 미설정)\n\n"
            f"{ctx[:4000]}"
        )
    else:
        out = f"{top_md}\n\n{table_md}\n\n---\n\n{out}"
    structured = {
        "sales_rep_id": rid,
        "pending_action_items": len(items),
        "companies": len(cos),
        "opportunities_portfolio": len(merged_opps),
        "focus_opportunity_ids": [o.id for o in top_focus],
    }
    return CrmAgentResult(out, ctx[:2000], ids, structured)


async def run(db: Session, settings: Settings, p: CrmAgentPayload) -> CrmAgentResult:
    from rag_agent.crm.models import Activity, Company, Opportunity

    if (
        p.sales_rep_id is not None
        and p.company_id is None
        and p.opportunity_id is None
    ):
        return await _run_for_sales_rep(db, settings, p)

    company: Company | None = None
    opp: Opportunity | None = None
    if p.opportunity_id:
        opp = db.get(Opportunity, p.opportunity_id)
        if not opp:
            return CrmAgentResult("사업기회를 찾을 수 없습니다.", "", [])
        company = db.get(Company, opp.company_id)
    elif p.company_id:
        company = db.get(Company, p.company_id)
        if not company:
            return CrmAgentResult("고객사를 찾을 수 없습니다.", "", [])

    if not company and not opp:
        return CrmAgentResult("고객사 또는 사업기회를 지정해 주세요.", "", [])

    if opp:
        acts = activities_for_opportunity(db, opp)
        stage = opp.stage
        header = f"[사업기회] id={opp.id} {opp.name} 단계={stage} 수주확률={opp.win_probability:.1%}"
    else:
        assert company is not None
        acts = (
            db.query(Activity)
            .filter(Activity.company_id == company.id)
            .order_by(Activity.created_at.desc())
            .limit(40)
            .all()
        )
        stage = "발굴"
        header = f"[고객사] id={company.id} {company.name}"

    ids = [a.id for a in acts[:40]]
    guide = STAGE_GUIDE.get(stage, STAGE_GUIDE["발굴"])
    lines = [header, f"[단계 가이드 템플릿]\n{guide}", "[최근 활동]"]
    for a in acts[:15]:
        t = a.created_at.isoformat() if a.created_at else ""
        lines.append(f"  id={a.id} {a.kind} {t} | {a.subject}")
    ctx = "\n".join(lines)

    sys_p = (
        "당신은 CRM의 '영업 활동 추천' 전담 에이전트입니다. "
        "단계 가이드와 최근 활동을 바탕으로 다음에 할 구체적 영업 행동(미팅·메일·내부 정합 등)을 "
        "한국어로 번호 목록으로 제안합니다. 실행 가능한 수준으로 적습니다."
    )
    user = f"{ctx}\n\n[사용자 요청]\n{p.message or '다음에 어떤 영업 활동을 하면 좋을지 추천해 주세요.'}"
    out = await llm_reply(settings, sys_p, user)
    if out is None:
        out = f"### 활동 추천 (LLM 미설정)\n\n{ctx}"
    return CrmAgentResult(out, ctx[:2000], ids)
