import json

from rag_agent.config import Settings
from rag_agent.mcp_client import call_mcp_tool
from rag_agent.state import AgentState


class RetrievalAgent:
    """MCP `rag_search`로 벡터 DB에서 근거를 가져옵니다."""

    id = "retrieval"

    async def run(self, state: AgentState, settings: Settings) -> None:
        if not state.search_query:
            state.retrieval_hits = []
            state.log(self.id, "skip", "검색 쿼리 없음")
            return
        raw = await call_mcp_tool(
            "rag_search",
            {
                "query": state.search_query,
                "n_results": 8,
                "rerank": settings.rag_search_rerank,
            },
        )
        try:
            state.retrieval_hits = json.loads(raw)
        except json.JSONDecodeError:
            state.retrieval_hits = []
            state.log(self.id, "parse_error", raw[:200])
            return
        state.log(self.id, "hits", str(len(state.retrieval_hits)))
