from rag_agent.state import AgentState


class VerifierAgent:
    """초안이 근거 부재·과잉 주장 패턴인지 간단히 점검합니다."""

    id = "verifier"

    async def run(self, state: AgentState) -> None:
        draft = (state.draft_answer or "").strip()
        if not state.retrieval_hits:
            state.verified_answer = draft
            state.log(self.id, "pass_no_hits", "")
            return

        risky = ("확실히", "무조건", "반드시", "100%")
        if any(w in draft for w in risky) and len(draft) < 40:
            state.verified_answer = (
                draft
                + "\n\n_검증: 단정적 표현이 감지되었습니다. 근거 문서를 다시 확인하세요._"
            )
            state.log(self.id, "flag_tone", "")
            return

        if not draft:
            state.verified_answer = "응답 생성에 실패했습니다."
            state.log(self.id, "empty", "")
            return

        state.verified_answer = draft
        state.log(self.id, "ok", "")
