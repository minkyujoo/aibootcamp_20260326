from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CrmAgentPayload:
    """에이전트 공통 입력."""

    message: str = ""
    company_id: int | None = None
    opportunity_id: int | None = None
    activity_text: str | None = None
    sales_rep_id: int | None = None


@dataclass
class CrmAgentResult:
    answer: str
    context_summary: str
    cited_activity_ids: list[int] = field(default_factory=list)
    structured: dict | None = None
