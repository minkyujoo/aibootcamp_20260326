"""AI 영업관리 포탈 REST API."""

from __future__ import annotations

import logging
import math
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from rag_agent.config import get_settings
from rag_agent.crm.agent_validate import agent_payload_error
from rag_agent.crm.agents.registry import REGISTRY, list_agents, run_agent
from rag_agent.crm.agents.types import CrmAgentPayload
from rag_agent.crm.db import get_db
from rag_agent.crm.file_extract import extract_text_from_bytes
from rag_agent.crm.mapping import suggest_mapping
from rag_agent.crm.action_seed import seed_actions_for_company_account, seed_actions_for_opportunity
from rag_agent.crm.models import ActionItem, Activity, Company, Opportunity, SalesRep
from rag_agent.crm.orchestrate import orchestrate_crm_query
from rag_agent.crm.probability import (
    activities_for_opportunity,
    recalculate_opportunity,
    win_probability_breakdown,
    win_probability_rationale_summary,
)
from rag_agent.crm.schemas import (
    ActionItemOut,
    ActionItemPatch,
    ActivityCreate,
    ActivityOut,
    CompanyCreate,
    CompanyDetailOut,
    CompanyOut,
    CompanyPatch,
    CrmAgentRunIn,
    CrmAgentRunOut,
    CrmOrchestrateIn,
    CrmOrchestrateOut,
    MappingSuggestIn,
    MappingSuggestOut,
    OpportunityCreate,
    OpportunityOut,
    OpportunityPatch,
    SalesRepCreate,
    SalesRepOut,
)

router = APIRouter()

_MAX_REPS = 10
_log = logging.getLogger(__name__)


def _json_safe_for_response(value: Any) -> Any:
    """FastAPI JSON 응답·Pydantic 검증에 안전한 값으로 정리."""
    if value is None:
        return None
    if isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe_for_response(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe_for_response(x) for x in value]
    return str(value)


def _opportunity_out_detail(db: Session, o: Opportunity) -> OpportunityOut:
    acts = activities_for_opportunity(db, o)
    bd = win_probability_breakdown(o, acts)
    summary = win_probability_rationale_summary(bd, float(o.win_probability))
    return OpportunityOut.model_validate(o).model_copy(
        update={"win_probability_rationale": summary}
    )


def _validate_agent_payload(agent_id: str, body: CrmAgentRunIn) -> None:
    err = agent_payload_error(agent_id, body)
    if err:
        raise HTTPException(status_code=400, detail=err)


@router.get("/sales-reps", response_model=list[SalesRepOut])
def list_reps(db: Session = Depends(get_db)) -> list[SalesRep]:
    return db.query(SalesRep).order_by(SalesRep.id).all()


@router.post("/sales-reps", response_model=SalesRepOut)
def create_rep(body: SalesRepCreate, db: Session = Depends(get_db)) -> SalesRep:
    n = db.query(SalesRep).count()
    if n >= _MAX_REPS:
        raise HTTPException(
            status_code=400,
            detail=f"영업 담당은 최대 {_MAX_REPS}명까지 등록할 수 있습니다.",
        )
    r = SalesRep(name=body.name.strip(), email=body.email)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@router.delete("/sales-reps/{rep_id}")
def delete_rep(rep_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    r = db.get(SalesRep, rep_id)
    if not r:
        raise HTTPException(status_code=404, detail="담당자 없음")
    db.query(Company).filter(Company.sales_rep_id == rep_id).update(
        {Company.sales_rep_id: None}
    )
    db.query(Opportunity).filter(Opportunity.sales_rep_id == rep_id).update(
        {Opportunity.sales_rep_id: None}
    )
    db.query(Activity).filter(Activity.sales_rep_id == rep_id).update(
        {Activity.sales_rep_id: None}
    )
    db.delete(r)
    db.commit()
    return {"status": "ok"}


@router.get("/sales-reps/{rep_id}/summary")
def rep_summary(rep_id: int, db: Session = Depends(get_db)) -> dict:
    r = db.get(SalesRep, rep_id)
    if not r:
        raise HTTPException(status_code=404, detail="담당자 없음")
    companies = (
        db.query(Company).filter(Company.sales_rep_id == rep_id).order_by(Company.id).all()
    )
    opps = (
        db.query(Opportunity)
        .filter(Opportunity.sales_rep_id == rep_id)
        .order_by(Opportunity.id)
        .all()
    )
    return {
        "rep": SalesRepOut.model_validate(r).model_dump(),
        "companies": [CompanyOut.model_validate(c).model_dump() for c in companies],
        "opportunities": [OpportunityOut.model_validate(o).model_dump() for o in opps],
    }


@router.get("/companies", response_model=list[CompanyOut])
def list_companies(db: Session = Depends(get_db)) -> list[Company]:
    return db.query(Company).order_by(Company.id).all()


@router.get("/companies/{company_id}", response_model=CompanyDetailOut)
def get_company(company_id: int, db: Session = Depends(get_db)) -> CompanyDetailOut:
    c = db.get(Company, company_id)
    if not c:
        raise HTTPException(status_code=404, detail="고객사 없음")
    oc = db.query(Opportunity).filter(Opportunity.company_id == company_id).count()
    ac = db.query(Activity).filter(Activity.company_id == company_id).count()
    out = CompanyDetailOut.model_validate(c)
    out.opportunities_count = oc
    out.activities_count = ac
    return out


@router.post("/companies", response_model=CompanyOut)
def create_company(body: CompanyCreate, db: Session = Depends(get_db)) -> Company:
    if body.sales_rep_id is not None and db.get(SalesRep, body.sales_rep_id) is None:
        raise HTTPException(status_code=400, detail="유효하지 않은 담당자 id")
    default_note = (
        "공공데이터포털(data.go.kr)·DART 전자공시 참고 시드 — SK 멤버사 중심"
    )
    note = (body.data_source_note or default_note).strip()
    if len(note) > 500:
        note = note[:500]
    dp = (body.dart_profile or "").strip() or None
    c = Company(
        name=body.name.strip(),
        biz_reg_no=(body.biz_reg_no or "").strip() or None,
        address=(body.address or "").strip() or None,
        industry=(body.industry or "").strip() or None,
        dart_profile=dp,
        data_source_note=note,
        sales_rep_id=body.sales_rep_id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    seed_actions_for_company_account(db, c.id)
    db.commit()
    return c


@router.patch("/companies/{company_id}", response_model=CompanyOut)
def patch_company(
    company_id: int, body: CompanyPatch, db: Session = Depends(get_db)
) -> Company:
    c = db.get(Company, company_id)
    if not c:
        raise HTTPException(status_code=404, detail="고객사 없음")
    data = body.model_dump(exclude_unset=True)
    if "sales_rep_id" in data:
        rid = data["sales_rep_id"]
        if rid is not None and db.get(SalesRep, rid) is None:
            raise HTTPException(status_code=400, detail="유효하지 않은 담당자 id")
        c.sales_rep_id = rid
    if "name" in data and data["name"] is not None:
        c.name = str(data["name"]).strip()
    if "biz_reg_no" in data:
        v = data["biz_reg_no"]
        c.biz_reg_no = None if v is None else (str(v).strip() or None)
    if "address" in data:
        v = data["address"]
        c.address = None if v is None else (str(v).strip() or None)
    if "industry" in data:
        v = data["industry"]
        c.industry = None if v is None else (str(v).strip() or None)
    if "data_source_note" in data and data["data_source_note"] is not None:
        c.data_source_note = str(data["data_source_note"])[:500]
    if "dart_profile" in data:
        v = data["dart_profile"]
        c.dart_profile = None if v is None else (str(v).strip() or None)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.get("/companies/{company_id}/action-items", response_model=list[ActionItemOut])
def list_company_action_items(
    company_id: int, db: Session = Depends(get_db)
) -> list[ActionItem]:
    if db.get(Company, company_id) is None:
        raise HTTPException(status_code=404, detail="고객사 없음")
    return (
        db.query(ActionItem)
        .filter(
            ActionItem.company_id == company_id,
            ActionItem.opportunity_id.is_(None),
        )
        .order_by(ActionItem.sort_order, ActionItem.id)
        .all()
    )


@router.get("/opportunities/{opp_id}/action-items", response_model=list[ActionItemOut])
def list_opportunity_action_items(
    opp_id: int, db: Session = Depends(get_db)
) -> list[ActionItem]:
    if db.get(Opportunity, opp_id) is None:
        raise HTTPException(status_code=404, detail="사업기회 없음")
    return (
        db.query(ActionItem)
        .filter(ActionItem.opportunity_id == opp_id)
        .order_by(ActionItem.sort_order, ActionItem.id)
        .all()
    )


@router.patch("/action-items/{item_id}", response_model=ActionItemOut)
def patch_action_item(
    item_id: int, body: ActionItemPatch, db: Session = Depends(get_db)
) -> ActionItem:
    it = db.get(ActionItem, item_id)
    if not it:
        raise HTTPException(status_code=404, detail="액션 항목 없음")
    data = body.model_dump(exclude_unset=True)
    if "status" in data and data["status"] is not None:
        it.status = data["status"]
    if "result_subject" in data:
        v = data["result_subject"]
        it.result_subject = None if v is None else str(v).strip() or None
    if "result_body" in data:
        v = data["result_body"]
        it.result_body = None if v is None else str(v).strip() or None
    db.add(it)
    db.commit()
    db.refresh(it)
    return it


@router.post("/action-items/{item_id}/execute-with-files", response_model=ActionItemOut)
async def action_item_execute_with_files(
    item_id: int,
    status: str = Form(...),
    result_subject: str = Form(""),
    result_body: str = Form(""),
    files: Annotated[list[UploadFile] | None, File()] = None,
    db: Session = Depends(get_db),
) -> ActionItem:
    if status not in ("in_progress", "done"):
        raise HTTPException(
            status_code=400, detail="status는 in_progress 또는 done 이어야 합니다."
        )
    it = db.get(ActionItem, item_id)
    if not it:
        raise HTTPException(status_code=404, detail="액션 항목 없음")
    excerpts: list[str] = []
    for uf in files or []:
        if not uf.filename:
            continue
        raw = await uf.read()
        if len(raw) > 25_000_000:
            raise HTTPException(status_code=400, detail=f"파일 너무 큼: {uf.filename}")
        text = extract_text_from_bytes(uf.filename, raw)
        excerpts.append(f"### {uf.filename}\n{text}")
    merged = "\n\n".join(excerpts)
    subj = result_subject.strip() or None
    body_txt = result_body.strip()
    if merged:
        body_txt = (
            body_txt + "\n\n--- 첨부에서 추출한 텍스트 ---\n" + merged
            if body_txt
            else "--- 첨부에서 추출한 텍스트 ---\n" + merged
        )
    it.status = status
    it.result_subject = subj
    it.result_body = body_txt.strip() or None
    it.result_attachment_excerpt = merged or None
    db.add(it)
    db.commit()
    db.refresh(it)
    return it


@router.get("/opportunities", response_model=list[OpportunityOut])
def list_opportunities(
    company_id: int | None = None, db: Session = Depends(get_db)
) -> list[Opportunity]:
    q = db.query(Opportunity).order_by(Opportunity.id)
    if company_id is not None:
        q = q.filter(Opportunity.company_id == company_id)
    return q.all()


@router.get("/opportunities/{opp_id}", response_model=OpportunityOut)
def get_opportunity(opp_id: int, db: Session = Depends(get_db)) -> OpportunityOut:
    o = db.get(Opportunity, opp_id)
    if not o:
        raise HTTPException(status_code=404, detail="사업기회 없음")
    return _opportunity_out_detail(db, o)


@router.post("/opportunities", response_model=OpportunityOut)
def create_opportunity(body: OpportunityCreate, db: Session = Depends(get_db)) -> OpportunityOut:
    if db.get(Company, body.company_id) is None:
        raise HTTPException(status_code=400, detail="유효하지 않은 company_id")
    if body.sales_rep_id is not None and db.get(SalesRep, body.sales_rep_id) is None:
        raise HTTPException(status_code=400, detail="유효하지 않은 sales_rep_id")
    o = Opportunity(
        company_id=body.company_id,
        name=body.name.strip(),
        project_type=body.project_type.strip(),
        stage=body.stage.strip(),
        sales_rep_id=body.sales_rep_id,
    )
    db.add(o)
    db.commit()
    db.refresh(o)
    recalculate_opportunity(db, o)
    db.refresh(o)
    seed_actions_for_opportunity(db, o)
    db.commit()
    return _opportunity_out_detail(db, o)


@router.delete("/opportunities/{opp_id}")
def delete_opportunity(opp_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    o = db.get(Opportunity, opp_id)
    if not o:
        raise HTTPException(status_code=404, detail="사업기회 없음")
    company_id = o.company_id
    db.query(Activity).filter(Activity.opportunity_id == opp_id).update(
        {Activity.opportunity_id: None}
    )
    db.query(ActionItem).filter(ActionItem.opportunity_id == opp_id).delete(
        synchronize_session=False
    )
    db.delete(o)
    db.commit()
    _recalc_opps_for_company(db, company_id)
    return {"status": "ok"}


@router.patch("/opportunities/{opp_id}", response_model=OpportunityOut)
def patch_opportunity(
    opp_id: int, body: OpportunityPatch, db: Session = Depends(get_db)
) -> OpportunityOut:
    o = db.get(Opportunity, opp_id)
    if not o:
        raise HTTPException(status_code=404, detail="사업기회 없음")
    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        o.name = str(data["name"]).strip()
    if "project_type" in data and data["project_type"] is not None:
        o.project_type = str(data["project_type"]).strip()
    if "stage" in data and data["stage"] is not None:
        o.stage = str(data["stage"]).strip()
    if "sales_rep_id" in data:
        rid = data["sales_rep_id"]
        if rid is not None and db.get(SalesRep, rid) is None:
            raise HTTPException(status_code=400, detail="유효하지 않은 담당자 id")
        o.sales_rep_id = rid
    if "company_id" in data and data["company_id"] is not None:
        cid = data["company_id"]
        if db.get(Company, cid) is None:
            raise HTTPException(status_code=400, detail="유효하지 않은 company_id")
        o.company_id = cid
    db.add(o)
    db.commit()
    recalculate_opportunity(db, o)
    db.refresh(o)
    return _opportunity_out_detail(db, o)


@router.post("/opportunities/{opp_id}/recalculate-probability", response_model=OpportunityOut)
def recalc_prob(opp_id: int, db: Session = Depends(get_db)) -> OpportunityOut:
    o = db.get(Opportunity, opp_id)
    if not o:
        raise HTTPException(status_code=404, detail="사업기회 없음")
    recalculate_opportunity(db, o)
    db.refresh(o)
    return _opportunity_out_detail(db, o)


def _recalc_opps_for_company(db: Session, company_id: int) -> None:
    for o in (
        db.query(Opportunity).filter(Opportunity.company_id == company_id).all()
    ):
        recalculate_opportunity(db, o)


@router.get("/activities", response_model=list[ActivityOut])
def list_activities(
    company_id: int | None = None,
    opportunity_id: int | None = None,
    db: Session = Depends(get_db),
) -> list[Activity]:
    q = db.query(Activity).order_by(Activity.created_at.desc())
    if company_id is not None:
        q = q.filter(Activity.company_id == company_id)
    if opportunity_id is not None:
        q = q.filter(Activity.opportunity_id == opportunity_id)
    return q.limit(200).all()


@router.post("/activities/suggest-mapping", response_model=MappingSuggestOut)
def suggest(body: MappingSuggestIn, db: Session = Depends(get_db)) -> MappingSuggestOut:
    s = suggest_mapping(db, body.text)
    return MappingSuggestOut(
        company_id=s.company_id,
        opportunity_id=s.opportunity_id,
        company_score=s.company_score,
        opportunity_score=s.opportunity_score,
        reason=s.reason,
    )


@router.post("/activities", response_model=ActivityOut)
def create_activity(body: ActivityCreate, db: Session = Depends(get_db)) -> Activity:
    raw_subj = (body.subject or "").strip()
    raw_txt = (body.body or "").strip()
    if not raw_subj and not raw_txt:
        raise HTTPException(status_code=400, detail="제목 또는 본문이 필요합니다.")
    subj = raw_subj or "(제목 없음)"
    txt = raw_txt

    text_for_map = f"{subj}\n{txt}".strip()
    cid = body.company_id
    oid = body.opportunity_id
    if cid is None and oid is None and text_for_map:
        s = suggest_mapping(db, text_for_map)
        cid = s.company_id
        oid = s.opportunity_id

    if cid is not None and db.get(Company, cid) is None:
        raise HTTPException(status_code=400, detail="유효하지 않은 company_id")
    if oid is not None:
        op = db.get(Opportunity, oid)
        if not op:
            raise HTTPException(status_code=400, detail="유효하지 않은 opportunity_id")
        if cid is not None and op.company_id != cid:
            raise HTTPException(
                status_code=400,
                detail="opportunity의 고객사와 company_id가 일치하지 않습니다.",
            )
    if body.sales_rep_id is not None and db.get(SalesRep, body.sales_rep_id) is None:
        raise HTTPException(status_code=400, detail="유효하지 않은 sales_rep_id")

    a = Activity(
        kind=body.kind,
        subject=subj,
        body=txt,
        company_id=cid,
        opportunity_id=oid,
        sales_rep_id=body.sales_rep_id,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    if a.opportunity_id:
        o = db.get(Opportunity, a.opportunity_id)
        if o:
            recalculate_opportunity(db, o)
    elif a.company_id:
        _recalc_opps_for_company(db, a.company_id)
    db.refresh(a)
    return a


@router.post("/activities/with-files", response_model=ActivityOut)
async def create_activity_with_files(
    kind: str = Form("note"),
    subject: str = Form(""),
    body: str = Form(""),
    company_id: str | None = Form(None),
    opportunity_id: str | None = Form(None),
    sales_rep_id: str | None = Form(None),
    files: Annotated[list[UploadFile] | None, File()] = None,
    db: Session = Depends(get_db),
) -> Activity:
    if kind not in ("note", "mail", "meeting", "opinion"):
        raise HTTPException(status_code=400, detail="kind는 note|mail|meeting|opinion")
    cid = int(company_id) if company_id not in (None, "") else None
    oid = int(opportunity_id) if opportunity_id not in (None, "") else None
    rid = int(sales_rep_id) if sales_rep_id not in (None, "") else None

    excerpts: list[str] = []
    for uf in files or []:
        if not uf.filename:
            continue
        raw = await uf.read()
        if len(raw) > 25_000_000:
            raise HTTPException(status_code=400, detail=f"파일 너무 큼: {uf.filename}")
        text = extract_text_from_bytes(uf.filename, raw)
        excerpts.append(f"### 파일: {uf.filename}\n{text}")

    subj_raw = subject.strip()
    full_body = body.strip()
    if excerpts:
        full_body += "\n\n--- 첨부에서 추출한 텍스트 ---\n" + "\n\n".join(excerpts)

    if not full_body.strip() and not subj_raw:
        raise HTTPException(
            status_code=400,
            detail="제목·본문 중 하나를 입력하거나 첨부 파일을 추가하세요.",
        )

    subj = subj_raw or "(제목 없음)"
    if not full_body.strip():
        full_body = subj_raw
    if cid is None and oid is None:
        s = suggest_mapping(db, f"{subj}\n{full_body}")
        cid = s.company_id
        oid = s.opportunity_id

    ac = ActivityCreate(
        kind=cast(Literal["mail", "meeting", "opinion", "note"], kind),
        subject=subj,
        body=full_body.strip(),
        company_id=cid,
        opportunity_id=oid,
        sales_rep_id=rid,
    )
    return create_activity(ac, db)


async def _run_crm_orchestrate(
    body: CrmOrchestrateIn, db: Session
) -> CrmOrchestrateOut:
    settings = get_settings()
    try:
        res = await orchestrate_crm_query(
            db,
            settings,
            message=body.message,
            current_menu=body.current_menu,
            context_company_id=body.context_company_id,
            context_opportunity_id=body.context_opportunity_id,
            context_sales_rep_id=body.context_sales_rep_id,
            use_rag=True,
        )
    except Exception as exc:  # noqa: BLE001
        _log.exception("orchestrate_crm_query 실패")
        raise HTTPException(
            status_code=502,
            detail=f"오케스트레이션 처리 중 서버 오류가 발생했습니다: {exc!s}",
        ) from exc
    routed = "orchestrator"
    reason = ""
    safe_structured: dict[str, Any] | None = None
    if isinstance(res.structured, dict):
        safe_structured = _json_safe_for_response(res.structured)
        routed = str(safe_structured.get("routed_agent") or "orchestrator")
        reason = str(safe_structured.get("routing_reason") or "")
    return CrmOrchestrateOut(
        routed_agent=routed,
        routing_reason=reason or res.context_summary,
        answer=res.answer,
        context_summary=res.context_summary,
        cited_activity_ids=res.cited_activity_ids[:40],
        structured=safe_structured,
    )


@router.get("/ping")
def crm_ping() -> dict[str, str]:
    """프론트·프록시가 올바른 백엔드에 붙었는지 확인용."""
    return {"service": "aicrm", "orchestrate": "POST /api/crm/orchestrate"}


@router.post("/orchestrate", response_model=CrmOrchestrateOut)
async def crm_orchestrate(
    body: CrmOrchestrateIn, db: Session = Depends(get_db)
) -> CrmOrchestrateOut:
    return await _run_crm_orchestrate(body, db)


@router.post("/ai-query", response_model=CrmOrchestrateOut)
async def crm_ai_query(
    body: CrmOrchestrateIn, db: Session = Depends(get_db)
) -> CrmOrchestrateOut:
    return await _run_crm_orchestrate(body, db)


@router.get("/agents")
def crm_agents_catalog() -> list[dict[str, str | list[str]]]:
    return list_agents()


@router.post("/agents/{agent_id}", response_model=CrmAgentRunOut)
async def crm_agent_run(
    agent_id: str, body: CrmAgentRunIn, db: Session = Depends(get_db)
) -> CrmAgentRunOut:
    if agent_id not in REGISTRY:
        raise HTTPException(status_code=404, detail=f"알 수 없는 에이전트: {agent_id}")
    _validate_agent_payload(agent_id, body)
    settings = get_settings()
    payload = CrmAgentPayload(
        message=body.message or "",
        company_id=body.company_id,
        opportunity_id=body.opportunity_id,
        activity_text=body.activity_text,
        sales_rep_id=body.sales_rep_id,
    )
    res = await run_agent(agent_id, db, settings, payload)
    return CrmAgentRunOut(
        agent=agent_id,
        answer=res.answer,
        context_summary=res.context_summary,
        cited_activity_ids=res.cited_activity_ids[:40],
        structured=res.structured,
    )
