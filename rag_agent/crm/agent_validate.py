"""CRM 에이전트 페이로드 검증 (API·오케스트레이터 공통)."""

from __future__ import annotations

from typing import Protocol


class _PayloadLike(Protocol):
    message: str
    company_id: int | None
    opportunity_id: int | None
    activity_text: str | None


def agent_payload_error(agent_id: str, body: _PayloadLike) -> str | None:
    if agent_id == "company_info" and body.company_id is None:
        return "company_info 에이전트는 company_id가 필요합니다."
    if agent_id in ("opportunity_info", "opp_rep_mapping", "win_probability"):
        if body.opportunity_id is None:
            return f"{agent_id} 에이전트는 opportunity_id가 필요합니다."
    if agent_id == "activity_mapping":
        text = (body.activity_text or body.message or "").strip()
        if not text:
            return "activity_mapping 에이전트는 message 또는 activity_text가 필요합니다."
    if agent_id == "activity_recommendation":
        sid = getattr(body, "sales_rep_id", None)
        if body.company_id is None and body.opportunity_id is None and sid is None:
            return (
                "activity_recommendation 에이전트는 company_id, opportunity_id 중 하나 또는 "
                "sales_rep_id(담당자 단위)가 필요합니다."
            )
    return None
