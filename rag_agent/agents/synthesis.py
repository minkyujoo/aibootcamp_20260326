from collections.abc import AsyncIterator

from rag_agent.config import Settings
from rag_agent.llm_client import chat_completions_create, llm_is_configured
from rag_agent.state import AgentState


class SynthesisAgent:
    """검색 결과를 바탕으로 초안 답변을 생성합니다."""

    id = "synthesis"

    @staticmethod
    def _build_context(state: AgentState) -> str:
        context_blocks = []
        for i, h in enumerate(state.retrieval_hits, start=1):
            doc = h.get("document") or ""
            src = str((h.get("metadata") or {}).get("source", "") or "")
            context_blocks.append(f"[{i}] (출처: {src})\n{doc}")
        return "\n\n".join(context_blocks)

    async def run(self, state: AgentState, settings: Settings) -> None:
        if not state.retrieval_hits:
            state.draft_answer = (
                "저장소에서 관련 문서를 찾지 못했습니다. 문서를 추가한 뒤 다시 질문해 주세요."
            )
            state.log(self.id, "no_hits", "")
            return

        context = self._build_context(state)

        if llm_is_configured(settings):
            state.draft_answer = await self._llm_answer(
                state.user_message, context, settings
            )
        else:
            state.draft_answer = (
                "### 검색 근거 요약 (LLM 미설정)\n\n"
                + context[:6000]
                + "\n\n_AOAI_API_KEY 또는 OPENAI_API_KEY를 설정하면 자연어 답변으로 합성됩니다._"
            )
        state.log(self.id, "draft_len", str(len(state.draft_answer or "")))

    async def stream_answer(
        self, state: AgentState, settings: Settings
    ) -> AsyncIterator[str]:
        """토큰(또는 블록) 단위로 합성 텍스트를 보냅니다. 종료 시 draft_answer를 채웁니다."""
        buf: list[str] = []
        try:
            if not state.retrieval_hits:
                msg = (
                    "저장소에서 관련 문서를 찾지 못했습니다. "
                    "문서를 추가한 뒤 다시 질문해 주세요."
                )
                buf.append(msg)
                yield msg
                state.log(self.id, "no_hits", "")
                return

            context = self._build_context(state)

            if not llm_is_configured(settings):
                text = (
                    "### 검색 근거 요약 (LLM 미설정)\n\n"
                    + context[:6000]
                    + "\n\n_AOAI_API_KEY 또는 OPENAI_API_KEY를 설정하면 자연어 답변으로 합성됩니다._"
                )
                buf.append(text)
                yield text
                return

            stream = await chat_completions_create(
                settings,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "당신은 근거 기반 한국어 어시스턴트입니다. "
                            "제공된 [번호] 인용 블록 안의 내용만 사용하고, "
                            "없는 사실은 추측하지 마세요. 답 끝에 사용한 근거 번호를 나열하세요."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"질문:\n{state.user_message}\n\n근거:\n{context[:12000]}",
                    },
                ],
                max_tokens=1024,
                stream=True,
            )
            async for event in stream:
                if not event.choices:
                    continue
                delta = event.choices[0].delta
                if delta and delta.content:
                    buf.append(delta.content)
                    yield delta.content
        finally:
            state.draft_answer = "".join(buf).strip()
            state.log(self.id, "draft_len", str(len(state.draft_answer or "")))

    async def _llm_answer(
        self, question: str, context: str, settings: Settings
    ) -> str:
        resp = await chat_completions_create(
            settings,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "당신은 근거 기반 한국어 어시스턴트입니다. "
                        "제공된 [번호] 인용 블록 안의 내용만 사용하고, "
                        "없는 사실은 추측하지 마세요. 답 끝에 사용한 근거 번호를 나열하세요."
                    ),
                },
                {
                    "role": "user",
                    "content": f"질문:\n{question}\n\n근거:\n{context[:12000]}",
                },
            ],
            max_tokens=1024,
            stream=False,
        )
        return (resp.choices[0].message.content or "").strip()
