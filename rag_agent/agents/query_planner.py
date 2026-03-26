from rag_agent.config import Settings
from rag_agent.llm_client import chat_completions_create, llm_is_configured
from rag_agent.state import AgentState


class QueryPlannerAgent:
    """사용자 발화에서 검색 쿼리를 확정합니다 (필요 시 LLM 보조)."""

    id = "query_planner"

    async def run(self, state: AgentState, settings: Settings) -> None:
        q = state.user_message.strip()
        if llm_is_configured(settings) and len(q) > 200:
            q = await self._llm_compress(q, settings)
        state.search_query = q or state.user_message.strip()
        state.log(self.id, "search_query", state.search_query or "")

    async def _llm_compress(self, text: str, settings: Settings) -> str:
        resp = await chat_completions_create(
            settings,
            messages=[
                {
                    "role": "system",
                    "content": "한국어 문서 검색용 짧은 쿼리 한 줄만 출력하세요.",
                },
                {"role": "user", "content": text[:8000]},
            ],
            max_tokens=120,
            stream=False,
        )
        choice = resp.choices[0].message.content
        return (choice or text).strip() or text
