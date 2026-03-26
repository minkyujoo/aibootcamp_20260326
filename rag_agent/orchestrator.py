"""4개 전문 에이전트를 순차 오케스트레이션합니다."""

from typing import Any, AsyncIterator

from rag_agent.agents import (
    QueryPlannerAgent,
    RetrievalAgent,
    SynthesisAgent,
    VerifierAgent,
)
from rag_agent.config import get_settings
from rag_agent.state import AgentState


class OrchestratorAgent:
    """파이프라인: 쿼리 계획 → MCP 검색 → 합성 → 검증."""

    id = "orchestrator"

    def __init__(self) -> None:
        self._planner = QueryPlannerAgent()
        self._retrieval = RetrievalAgent()
        self._synthesis = SynthesisAgent()
        self._verifier = VerifierAgent()

    async def run(self, user_message: str, session_id: str) -> dict:
        settings = get_settings()
        state = AgentState(user_message=user_message, session_id=session_id)
        state.log(self.id, "start", session_id)

        await self._planner.run(state, settings)
        await self._retrieval.run(state, settings)
        await self._synthesis.run(state, settings)
        await self._verifier.run(state)

        state.log(self.id, "done", "")
        return {
            "answer": state.verified_answer,
            "search_query": state.search_query,
            "hits": state.retrieval_hits,
            "trace": state.agent_trace,
        }

    async def run_stream(
        self, user_message: str, session_id: str
    ) -> AsyncIterator[dict[str, Any]]:
        """SSE용 이벤트 스트림: trace, hits, token, done."""
        settings = get_settings()
        state = AgentState(user_message=user_message, session_id=session_id)
        state.log(self.id, "start", session_id)
        yield {"event": "trace", "data": list(state.agent_trace)}

        await self._planner.run(state, settings)
        yield {"event": "trace", "data": list(state.agent_trace)}

        await self._retrieval.run(state, settings)
        yield {"event": "trace", "data": list(state.agent_trace)}
        yield {"event": "hits", "data": state.retrieval_hits}

        async for token in self._synthesis.stream_answer(state, settings):
            yield {"event": "token", "data": token}

        await self._verifier.run(state)
        yield {"event": "trace", "data": list(state.agent_trace)}
        state.log(self.id, "done", "")
        yield {
            "event": "done",
            "data": {
                "answer": state.verified_answer,
                "search_query": state.search_query,
                "hits": state.retrieval_hits,
                "trace": state.agent_trace,
            },
        }
