from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentState:
    """오케스트레이션 파이프라인 공유 상태."""

    user_message: str
    session_id: str
    search_query: str | None = None
    retrieval_hits: list[dict[str, Any]] = field(default_factory=list)
    draft_answer: str | None = None
    verified_answer: str | None = None
    agent_trace: list[dict[str, str]] = field(default_factory=list)

    def log(self, agent_id: str, step: str, detail: str = "") -> None:
        self.agent_trace.append(
            {"agent": agent_id, "step": step, "detail": detail[:500]}
        )
