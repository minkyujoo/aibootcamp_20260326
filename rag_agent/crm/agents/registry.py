"""CRM 전문 에이전트 레지스트리."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from rag_agent.config import Settings
from rag_agent.crm.agents import (
    activity_mapping,
    activity_recommendation,
    company_info,
    opp_rep_mapping,
    opportunity_info,
    win_probability,
)
from rag_agent.crm.agents.types import CrmAgentPayload, CrmAgentResult
from sqlalchemy.orm import Session

AgentFn = Callable[[Session, Settings, CrmAgentPayload], Awaitable[CrmAgentResult]]

REGISTRY: dict[str, AgentFn] = {
    "company_info": company_info.run,
    "opportunity_info": opportunity_info.run,
    "opp_rep_mapping": opp_rep_mapping.run,
    "win_probability": win_probability.run,
    "activity_mapping": activity_mapping.run,
    "activity_recommendation": activity_recommendation.run,
}

AGENT_META: list[dict[str, str | list[str]]] = [
    {
        "id": "company_info",
        "title": "고객사 정보 문의",
        "description": "고객사 마스터·연결 기회·활동 요약 기반 질의응답",
        "requires": ["company_id"],
    },
    {
        "id": "opportunity_info",
        "title": "사업기회 정보 문의",
        "description": "사업기회 상세·관련 활동 기반 질의응답",
        "requires": ["opportunity_id"],
    },
    {
        "id": "opp_rep_mapping",
        "title": "사업기회/영업담당 매핑",
        "description": "고객사·기회 담당 일관성 및 담당자 후보 제안",
        "requires": ["opportunity_id"],
    },
    {
        "id": "win_probability",
        "title": "사업기회 수주확률 계산·설명",
        "description": "규칙 엔진 분해 수치와 자연어 설명",
        "requires": ["opportunity_id"],
    },
    {
        "id": "activity_mapping",
        "title": "영업활동 매핑",
        "description": "본문 기반 고객사·사업기회 매핑 제안 및 설명",
        "requires": ["message 또는 activity_text"],
    },
    {
        "id": "activity_recommendation",
        "title": "영업 활동 추천",
        "description": "단계 가이드·최근 활동·Action item 기반 다음 액션 제안",
        "requires": ["company_id 또는 opportunity_id 또는 sales_rep_id"],
    },
]


def list_agents() -> list[dict[str, str | list[str]]]:
    return list(AGENT_META)


async def run_agent(
    agent_id: str,
    db: Session,
    settings: Settings,
    payload: CrmAgentPayload,
) -> CrmAgentResult:
    fn = REGISTRY.get(agent_id)
    if fn is None:
        raise KeyError(agent_id)
    return await fn(db, settings, payload)
