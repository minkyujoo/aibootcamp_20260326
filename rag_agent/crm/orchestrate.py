"""CRM 멀티에이전트 오케스트레이션: 질문 의도 → 에이전트 선택(A2A) + 선택적 MCP RAG."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

_log = logging.getLogger(__name__)

from sqlalchemy.orm import Session

from rag_agent.config import Settings
from rag_agent.crm.agent_validate import agent_payload_error
from rag_agent.crm.agents.registry import REGISTRY, run_agent
from rag_agent.crm.agents.types import CrmAgentPayload, CrmAgentResult
from rag_agent.crm.mapping import suggest_mapping
from rag_agent.crm.models import Company, Opportunity, SalesRep
from rag_agent.crm.schemas import CrmAgentRunIn
from rag_agent.llm_client import chat_completions_create, llm_is_configured
from rag_agent.mcp_client import call_mcp_tool

VALID_AGENTS = frozenset(REGISTRY.keys())


def normalize_crm_user_message(message: str) -> str:
    """연속 공백·앞뒤 공백 정리(라우팅·RAG·에이전트 입력 공통)."""
    t = (message or "").strip()
    return re.sub(r"\s+", " ", t)


ORCH_SYSTEM = """당신은 AI 영업관리 포탈의 AI 영업관리 Agent(오케스트레이터)입니다. 사용자 질문과 화면 맥락을 보고
아래 전문 에이전트 중 정확히 하나를 선택하고, 필요한 ID를 채웁니다.

작업 순서(내부 추론): 질문 의도를 한 줄로 정리한 뒤, 규칙에 맞는 agent_id와 company_id/opportunity_id를 고릅니다.

에이전트 목록:
- company_info: 고객사 마스터·연결 기회·활동 요약 질문 (company_id 필수)
- opportunity_info: 특정 사업기회 상세·관련 활동 질문 (opportunity_id 필수)
- opp_rep_mapping: 사업기회와 영업담당 배정·일관성 (opportunity_id 필수)
- win_probability: 수주확률 수치·근거 설명 (opportunity_id 필수)
- activity_mapping: 메일/회의록/의견 텍스트를 고객사·기회에 매핑 (activity_text에 본문; 긴 활동 본문일 때)
- activity_recommendation: 다음 영업 액션·단계별 추천 (company_id 또는 opportunity_id 또는 context_sales_rep_id로 담당자 단위)

규칙:
1) 사용자가 특정 고객사만 물어보면 company_info + 해당 company_id.
2) 사업기회 이름/ERP/M365 등 기회 단위 질문은 opportunity_info 등 opportunity_id 필요 에이전트.
3) "매핑", "어느 고객사", "어느 기회"처럼 활동 본문 분석이면 activity_mapping + activity_text에 사용자 메시지 전체 또는 본문.
4) "뭐 할까", "다음 단계", "추천"이면 activity_recommendation + 가능한 경우 company_id 또는 opportunity_id.
5) 카탈로그의 id만 사용. 없으면 null.
6) [화면 맥락]의 context_company_id / context_opportunity_id / context_sales_rep_id를 JSON의 company_id·opportunity_id·sales_rep_id에 맞게 반영합니다. "이 고객사"→company_id, "이 담당자"·담당자별 액션→activity_recommendation과 sales_rep_id=context_sales_rep_id. 질문에 영업담당 이름이 나오면 카탈로그의 영업담당 목록과 매칭해 sales_rep_id를 채웁니다.
7) 특정 고객사 소속 기회 중 가장 유망·유력·수주확률이 가장 높은 기회를 묻는 경우 agent_id는 win_probability이고, 카탈로그에서 그 company_id의 사업기회 중 win_probability 값이 최대인 opportunity_id 하나를 고릅니다.
8) [화면 맥락]에 context_sales_rep_id가 있거나 메뉴가 reps이고, 질문에 액션/Action item/할 일 등 **담당자 포트폴리오의 할 일**이 보이면 반드시 activity_recommendation입니다. 이 경우 win_probability·opportunity_info로 바꾸지 마세요.
9) [MCP RAG 검색 요약]은 참고용 예시일 뿐입니다. 사용자 문장의 실제 의도(특히 담당자+액션)와 다르면 RAG 내용을 따르지 마세요.

반드시 JSON 한 덩어리만 출력 (코드펜스 없이):
{"agent_id":"...","company_id":null,"opportunity_id":null,"sales_rep_id":null,"activity_text":null,"rationale_ko":"한 줄 이유"}
activity_text는 activity_mapping일 때만 문자열, 아니면 null. sales_rep_id는 담당자 단위(activity_recommendation 등)일 때만 숫자, 아니면 null.
"""


def _catalog(db: Session, max_co: int = 80, max_opp: int = 200, max_rep: int = 80) -> str:
    cos = db.query(Company).order_by(Company.id).limit(max_co).all()
    opps = db.query(Opportunity).order_by(Opportunity.id).limit(max_opp).all()
    reps = db.query(SalesRep).order_by(SalesRep.id).limit(max_rep).all()
    co_lines = [f'{{"id":{c.id},"name":{json.dumps(c.name, ensure_ascii=False)}}}' for c in cos]
    opp_lines = [
        f'{{"id":{o.id},"name":{json.dumps(o.name, ensure_ascii=False)},"company_id":{o.company_id}}}'
        for o in opps
    ]
    rep_lines = [f'{{"id":{r.id},"name":{json.dumps(r.name, ensure_ascii=False)}}}' for r in reps]
    return (
        "고객사:\n["
        + ",\n".join(co_lines)
        + "]\n\n사업기회:\n["
        + ",\n".join(opp_lines)
        + "]\n\n영업담당:\n["
        + ",\n".join(rep_lines)
        + "]"
    )


async def _rag_context(message: str, settings: Settings) -> tuple[list[str], str]:
    snippets: list[str] = []
    raw_summary = ""
    try:
        raw = await call_mcp_tool(
            "rag_search",
            {"query": message[:2000], "n_results": 5, "rerank": settings.rag_search_rerank},
        )
        hits = json.loads(raw)
        if isinstance(hits, list):
            for h in hits[:5]:
                if isinstance(h, dict):
                    doc = str(h.get("document", ""))[:1200]
                    if doc.strip():
                        snippets.append(doc.strip())
        raw_summary = "\n---\n".join(snippets)[:6000]
    except Exception:  # noqa: BLE001
        pass
    return snippets, raw_summary


def _fuzzy_resolve_ids(
    db: Session, message: str, company_id: int | None, opportunity_id: int | None
) -> tuple[int | None, int | None]:
    msg = message
    if company_id is None:
        cos = db.query(Company).all()
        best: tuple[int, int] | None = None
        for c in cos:
            if c.name and c.name in msg:
                ln = len(c.name)
                if best is None or ln > best[1]:
                    best = (c.id, ln)
        if best:
            company_id = best[0]
    if opportunity_id is None:
        opps = db.query(Opportunity).all()
        best_o: tuple[int, int] | None = None
        for o in opps:
            if o.name and o.name in msg:
                ln = len(o.name)
                if best_o is None or ln > best_o[1]:
                    best_o = (o.id, ln)
        if best_o:
            opportunity_id = best_o[0]
    return company_id, opportunity_id


def _fuzzy_resolve_sales_rep_id(db: Session, message: str) -> int | None:
    """본문에 포함된 영업담당 표시명과 가장 긴 일치로 id 추론."""
    reps = db.query(SalesRep).order_by(SalesRep.id).all()
    best: tuple[int, int] | None = None
    for r in reps:
        n = (r.name or "").strip()
        if len(n) < 2:
            continue
        if n in message:
            ln = len(n)
            if best is None or ln > best[1]:
                best = (r.id, ln)
    return best[0] if best else None


def _best_opportunity_id_for_company(db: Session, company_id: int) -> int | None:
    o = (
        db.query(Opportunity)
        .filter(Opportunity.company_id == company_id)
        .order_by(Opportunity.win_probability.desc(), Opportunity.id.desc())
        .first()
    )
    return o.id if o else None


def _should_resolve_best_opportunity_for_company(message: str) -> bool:
    """'가장 유력한 사업기회'·'수주확률이 가장 높은 기회' 등 고객사 단위 최상위 기회 질문."""
    m = message.strip()
    compact = m.replace(" ", "").replace("\n", "")
    if "가장유력" in compact or "가장유망" in compact:
        return True
    if "유력한" in m and ("기회" in m or "사업기회" in m):
        return True
    if "가장" in m and "유력" in m and ("기회" in m or "사업" in m):
        return True
    if "최고" in m and ("수주확률" in compact or ("수주" in m and "확률" in m)):
        return True
    # "가장 수주 확률이 높은 사업기회", "확률 제일 높은 기회" 등
    if "가장" in m and "확률" in m and ("사업기회" in m or "기회" in m):
        return True
    if "가장" in m and "높은" in m and "확률" in m:
        return True
    if ("제일" in m or "가장" in m) and "확률" in m and ("기회" in m or "사업기회" in m):
        return True
    low = m.lower()
    if "most promising" in low or "best opportunity" in low or "highest win" in low:
        return True
    return False


def _mentions_action_item_intent(message: str) -> bool:
    """담당자 단위 Action item·할 일 목록·추천 질의인지 (수주확률 질의와 구분)."""
    m = message.strip()
    low = m.lower()
    compact = m.replace(" ", "").replace("\n", "")
    if "액션" in m or "액션아이템" in compact:
        return True
    if "actionitem" in compact or "action item" in low:
        return True
    if "action" in low and "item" in low:
        return True
    if "할일" in compact or "할 일" in m:
        return True
    if "to-do" in low or "todo" in low:
        return True
    return False


def _should_force_rep_activity_recommendation(
    message: str,
    context_sales_rep_id: int | None,
    current_menu: str | None,
) -> bool:
    """RAG/LLM이 win_probability 등으로 오분류하는 담당자 Action item 질의를 고정."""
    if _should_resolve_best_opportunity_for_company(message):
        return False
    if not _mentions_action_item_intent(message):
        return False
    menu_l = (current_menu or "").strip().lower()
    if context_sales_rep_id is not None:
        return True
    if menu_l == "reps" and (
        "담당" in message or "이 담당" in message or "담당의" in message or "영업담당" in message
    ):
        return True
    return False


def _apply_rep_action_recommendation_route_override(
    routed: dict[str, Any],
    message: str,
    context_sales_rep_id: int | None,
    current_menu: str | None,
) -> None:
    if not _should_force_rep_activity_recommendation(
        message, context_sales_rep_id, current_menu
    ):
        return
    routed["agent_id"] = "activity_recommendation"
    routed["company_id"] = None
    routed["opportunity_id"] = None
    routed["activity_text"] = None
    routed["rationale_ko"] = (
        "담당자 Action item·할 일 질의 → activity_recommendation 고정 "
        "(RAG의 수주확률 예시와 무관)"
    )


def _skip_best_opportunity_autopick(message: str, agent_id: str) -> bool:
    """수주확률 최고 기회 자동 선택을 하지 않을 에이전트(본문 매핑 등)."""
    if agent_id == "activity_recommendation":
        return True
    # 긴 활동 본문 매핑은 유지하되, '가장 수주확률 높은 기회' 류 질문이면 재분류 허용
    if agent_id == "activity_mapping" and not _should_resolve_best_opportunity_for_company(message):
        return True
    return False


def _merge_ui_context_into_route(
    routed: dict[str, Any],
    db: Session,
    context_company_id: int | None,
    context_opportunity_id: int | None,
) -> None:
    cid = routed.get("company_id")
    oid = routed.get("opportunity_id")
    if cid is None and context_company_id is not None and db.get(Company, context_company_id) is not None:
        routed["company_id"] = context_company_id
    if oid is None and context_opportunity_id is not None and db.get(Opportunity, context_opportunity_id) is not None:
        routed["opportunity_id"] = context_opportunity_id
    cid2 = routed.get("company_id")
    oid2 = routed.get("opportunity_id")
    if cid2 is None and isinstance(oid2, int):
        o = db.get(Opportunity, oid2)
        if o is not None:
            routed["company_id"] = o.company_id


def _parse_llm_json(text: str) -> dict[str, Any] | None:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```\s*$", "", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", t)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
        return None


def _heuristic_route(
    db: Session, message: str, menu: str | None
) -> dict[str, Any]:
    m = message.strip()
    low = m.lower()

    if "매핑" in m or "어느 고객" in m or "어느 사업" in m or len(m) > 400:
        sm = suggest_mapping(db, m)
        return {
            "agent_id": "activity_mapping",
            "company_id": sm.company_id,
            "opportunity_id": sm.opportunity_id,
            "activity_text": m,
            "rationale_ko": "휴리스틱: 활동/긴 본문 → activity_mapping",
        }

    if menu == "reps" and ("액션" in m or "action" in low or "추천" in m or "item" in low):
        return {
            "agent_id": "activity_recommendation",
            "company_id": None,
            "opportunity_id": None,
            "activity_text": None,
            "rationale_ko": "휴리스틱: 영업담당 화면 + 액션/추천",
        }
    if ("담당자" in m or "이 담당" in m or "담당의" in m) and (
        "액션" in m or "action" in low or "추천" in m or "item" in low
    ):
        return {
            "agent_id": "activity_recommendation",
            "company_id": None,
            "opportunity_id": None,
            "activity_text": None,
            "rationale_ko": "휴리스틱: 담당자·액션 추천",
        }

    if menu == "opportunities" or "수주" in m or "확률" in m or "단계" in m:
        cid, oid = _fuzzy_resolve_ids(db, m, None, None)
        if oid is not None:
            aid = "win_probability" if ("확률" in m or "수주" in m) else "opportunity_info"
            return {
                "agent_id": aid,
                "company_id": cid,
                "opportunity_id": oid,
                "activity_text": None,
                "rationale_ko": "휴리스틱: 사업기회 맥락",
            }

    if menu == "companies" or "고객사" in m:
        cid, oid = _fuzzy_resolve_ids(db, m, None, None)
        if cid is not None:
            return {
                "agent_id": "company_info",
                "company_id": cid,
                "opportunity_id": oid,
                "activity_text": None,
                "rationale_ko": "휴리스틱: 고객사 맥락",
            }

    cid, oid = _fuzzy_resolve_ids(db, m, None, None)
    if oid is not None:
        return {
            "agent_id": "opportunity_info",
            "company_id": cid,
            "opportunity_id": oid,
            "activity_text": None,
            "rationale_ko": "휴리스틱: 본문에 사업기회명 일치",
        }
    if cid is not None:
        return {
            "agent_id": "company_info",
            "company_id": cid,
            "opportunity_id": None,
            "activity_text": None,
            "rationale_ko": "휴리스틱: 본문에 고객사명 일치",
        }

    if "추천" in m or "다음" in m or "액션" in m:
        rcid, roid = _fuzzy_resolve_ids(db, m, None, None)
        if rcid is not None or roid is not None:
            return {
                "agent_id": "activity_recommendation",
                "company_id": rcid,
                "opportunity_id": roid,
                "activity_text": None,
                "rationale_ko": "휴리스틱: 추천 키워드 + 이름 매칭",
            }

    return {
        "agent_id": "activity_mapping",
        "company_id": None,
        "opportunity_id": None,
        "activity_text": m,
        "rationale_ko": "폴백: activity_mapping으로 본문 분석",
    }


def _coerce_optional_int(v: Any) -> int | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v == int(v):
        return int(v)
    if isinstance(v, str) and v.strip().lstrip("-").isdigit():
        return int(v.strip())
    return None


def _validate_and_fill(
    db: Session, d: dict[str, Any], message: str
) -> tuple[str, int | None, int | None, str | None, str]:
    agent_id = str(d.get("agent_id") or "").strip()
    if agent_id not in VALID_AGENTS:
        raise ValueError(f"알 수 없는 agent_id: {agent_id}")
    cid = d.get("company_id")
    oid = d.get("opportunity_id")
    at = d.get("activity_text")
    reason = str(d.get("rationale_ko") or "모델 라우팅")

    company_id = _coerce_optional_int(cid)
    opportunity_id = _coerce_optional_int(oid)
    activity_text = str(at).strip() if at else None

    company_id, opportunity_id = _fuzzy_resolve_ids(db, message, company_id, opportunity_id)

    if company_id is not None and db.get(Company, company_id) is None:
        company_id = None
    if opportunity_id is not None and db.get(Opportunity, opportunity_id) is None:
        opportunity_id = None

    if agent_id == "activity_mapping" and not (activity_text or "").strip():
        activity_text = message.strip() or None

    return agent_id, company_id, opportunity_id, activity_text, reason


async def _orchestrate_with_rag_block(
    db: Session,
    settings: Settings,
    *,
    message: str,
    current_menu: str | None = None,
    context_company_id: int | None = None,
    context_opportunity_id: int | None = None,
    context_sales_rep_id: int | None = None,
    rag_snippets: list[str],
    rag_block: str,
) -> CrmAgentResult:
    """RAG 스니펫이 준비된 뒤 라우팅·검증·전문 에이전트 실행(LangGraph 두 번째 노드)."""
    message = normalize_crm_user_message(message)
    catalog = _catalog(db)
    menu_hint = current_menu or "알 수 없음"
    user_block = f"현재 화면 메뉴: {menu_hint}\n\n사용자 질문:\n{message}\n"
    if (
        context_company_id is not None
        or context_opportunity_id is not None
        or context_sales_rep_id is not None
    ):
        user_block += (
            "\n[화면에서 선택된 맥락 — 질문에 이름/id가 없으면 우선 적용]\n"
            f"context_company_id={context_company_id}, "
            f"context_opportunity_id={context_opportunity_id}, "
            f"context_sales_rep_id={context_sales_rep_id}\n"
        )
    if rag_block and not _should_force_rep_activity_recommendation(
        message, context_sales_rep_id, current_menu
    ):
        user_block += f"\n[MCP RAG 검색 요약]\n{rag_block}\n"
    elif rag_block:
        user_block += (
            "\n[MCP RAG 검색 요약]\n"
            "(이 질의는 담당자 Action item용이므로 RAG 예시는 생략 — 수주확률 질의와 혼동 방지)\n"
        )

    routed: dict[str, Any] | None = None
    route_reason = ""

    if llm_is_configured(settings):
        try:
            resp = await chat_completions_create(
                settings,
                messages=[
                    {"role": "system", "content": ORCH_SYSTEM + "\n\n카탈로그:\n" + catalog},
                    {"role": "user", "content": user_block},
                ],
                max_tokens=600,
            )
            choice = resp.choices[0].message
            content = (choice.content or "").strip()
            routed = _parse_llm_json(content)
        except Exception:  # noqa: BLE001
            routed = None

    if routed is None:
        routed = _heuristic_route(db, message, current_menu)
        route_reason = str(routed.get("rationale_ko") or "휴리스틱")
    else:
        route_reason = str(routed.get("rationale_ko") or "LLM 라우팅")

    _merge_ui_context_into_route(routed, db, context_company_id, context_opportunity_id)
    _apply_rep_action_recommendation_route_override(
        routed, message, context_sales_rep_id, current_menu
    )
    route_reason = str(routed.get("rationale_ko") or route_reason).strip()

    try:
        agent_id, company_id, opportunity_id, activity_text, r2 = _validate_and_fill(
            db, routed, message
        )
        r2 = str(r2 or "").strip()
        if r2 and r2 != route_reason:
            route_reason = f"{route_reason} → {r2}"
    except ValueError as e:
        return CrmAgentResult(
            answer=f"라우팅 오류: {e}",
            context_summary="",
            cited_activity_ids=[],
            structured={"error": str(e), "rag_snippets": rag_snippets},
        )

    if company_id is None and opportunity_id is not None:
        o_fill = db.get(Opportunity, opportunity_id)
        if o_fill is not None:
            company_id = o_fill.company_id

    auto_picked_best_opp = False
    if (
        _should_resolve_best_opportunity_for_company(message)
        and company_id is not None
        and not _skip_best_opportunity_autopick(message, agent_id)
        and not (
            context_sales_rep_id is not None and _mentions_action_item_intent(message)
        )
    ):
        oid_best = _best_opportunity_id_for_company(db, company_id)
        if oid_best is None:
            return CrmAgentResult(
                answer=(
                    "현재 맥락의 고객사에 등록된 사업기회가 없어, "
                    "가장 유력한 기회를 골라 드릴 수 없습니다."
                ),
                context_summary=route_reason,
                cited_activity_ids=[],
                structured={
                    "routed_agent": "orchestrator",
                    "routing_reason": route_reason,
                    "rag_snippets": rag_snippets[:3],
                },
            )
        prev_agent = agent_id
        opportunity_id = oid_best
        agent_id = "win_probability"
        auto_picked_best_opp = True
        route_reason = (
            f"{route_reason} | 해당 고객사 소속 수주확률 최상 기회 자동 선택 "
            f"(opportunity_id={oid_best}, 이전 에이전트 후보={prev_agent})"
        )

    message_for_agent = message
    if auto_picked_best_opp and opportunity_id is not None:
        o_pick = db.get(Opportunity, opportunity_id)
        if o_pick is not None:
            co = db.get(Company, company_id) if company_id is not None else None
            co_name = co.name if co else f"고객사 id={company_id}"
            message_for_agent = (
                f"{message}\n\n[시스템 안내] 답변 대상 사업기회: 「{o_pick.name}」(id={o_pick.id}). "
                f"「{co_name}」 소속 등록 기회 중 저장된 수주확률(win_probability)이 가장 높은 기회로 자동 선택되었습니다. "
                "기회 이름·단계·수주확률 수치와 규칙 기반 근거를 바탕으로 왜 상대적으로 유력한지 한국어로 요약하세요."
            )

    rep_ctx: int | None = None
    if context_sales_rep_id is not None and db.get(SalesRep, context_sales_rep_id) is not None:
        rep_ctx = context_sales_rep_id
    if agent_id == "activity_recommendation":
        if rep_ctx is None:
            sid = _coerce_optional_int(routed.get("sales_rep_id"))
            if sid is not None and db.get(SalesRep, sid) is not None:
                rep_ctx = sid
        if rep_ctx is None and _mentions_action_item_intent(message):
            fr = _fuzzy_resolve_sales_rep_id(db, message)
            if fr is not None:
                rep_ctx = fr
        if rep_ctx is None and (current_menu or "").strip().lower() == "reps":
            if db.query(SalesRep).count() == 1:
                lone = db.query(SalesRep).first()
                if lone is not None:
                    rep_ctx = lone.id

    payload = CrmAgentPayload(
        message=message_for_agent,
        company_id=company_id,
        opportunity_id=opportunity_id,
        activity_text=activity_text,
        sales_rep_id=rep_ctx,
    )

    stub = CrmAgentRunIn(
        message=message,
        company_id=company_id,
        opportunity_id=opportunity_id,
        activity_text=activity_text,
        sales_rep_id=rep_ctx,
    )
    v_err = agent_payload_error(agent_id, stub)
    if v_err:
        if agent_id == "activity_recommendation":
            hint = (
                "영업담당 메뉴에서 담당자를 선택하거나 질문에 영업담당 이름을 넣어 주세요. "
                "담당자가 한 명뿐이면 같은 메뉴에서 자동 맥락이 붙습니다. "
                "고객사·사업기회 단위 추천이면 해당 화면에서 맥락을 주거나 이름을 문장에 포함하세요."
            )
        else:
            hint = (
                "영업담당 메뉴에서 담당자를 선택한 뒤 질문하거나, "
                "질문에 고객사명·사업기회명을 넣거나 고객사/사업기회 화면에서 맥락을 주면 자동 매칭이 쉬워집니다."
            )
        return CrmAgentResult(
            answer=f"선택된 에이전트({agent_id})에 필요한 정보가 부족합니다: {v_err}\n{hint}",
            context_summary=route_reason,
            cited_activity_ids=[],
            structured={
                "routed_agent": agent_id,
                "routing_reason": route_reason,
                "rag_snippets": rag_snippets[:3],
            },
        )

    try:
        res = await run_agent(agent_id, db, settings, payload)
    except Exception as exc:  # noqa: BLE001
        _log.exception("CRM run_agent 실패 agent_id=%s", agent_id)
        return CrmAgentResult(
            answer=f"에이전트 실행 중 오류가 발생했습니다. 잠시 후 다시 시도하거나 관리자에게 문의하세요. ({exc!s})",
            context_summary=route_reason,
            cited_activity_ids=[],
            structured={
                "error": str(exc),
                "routed_agent": agent_id,
                "routing_reason": route_reason,
                "rag_snippets": rag_snippets[:3],
            },
        )
    structured = dict(res.structured or {})
    structured["routed_agent"] = agent_id
    structured["routing_reason"] = route_reason
    structured["rag_snippets"] = rag_snippets[:5]
    return CrmAgentResult(
        answer=res.answer,
        context_summary=res.context_summary,
        cited_activity_ids=res.cited_activity_ids,
        structured=structured,
    )


async def orchestrate_crm_query(
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
    """MCP RAG(노드 1) → 라우팅·전문 에이전트(노드 2)를 LangGraph로 실행합니다."""
    from rag_agent.crm.langgraph_orch import run_crm_orch_graph

    return await run_crm_orch_graph(
        db,
        settings,
        message=message,
        current_menu=current_menu,
        context_company_id=context_company_id,
        context_opportunity_id=context_opportunity_id,
        context_sales_rep_id=context_sales_rep_id,
        use_rag=use_rag,
    )
