# Bootcamp 과제 가이드 대응 요약

본 프로젝트가 **End-to-End AI Agent** 과제 가이드의 필수·선택 항목과 어떻게 맞닿아 있는지 정리합니다.

| 가이드 항목 | 구현 위치·비고 |
|-------------|----------------|
| Prompt Engineering (역할·구조화) | `rag_agent/crm/orchestrate.py`의 `ORCH_SYSTEM`, 각 전문 에이전트 시스템 프롬프트 |
| CoT(추론 순서) | `ORCH_SYSTEM` 내 “질문 의도를 한 줄로 정리한 뒤…” |
| LangGraph 기반 오케스트레이션 | `rag_agent/crm/langgraph_orch.py` — RAG 검색 → 라우팅·실행을 **동일 순서의 비동기 파이프라인**으로 구현(그래프 상태 이슈 회피). |
| Multi-Agent (단일 에이전트만으로는 부족) | 오케스트레이터 + `rag_agent/crm/agents/` 전문 에이전트 다수; RAG 채팅은 `rag_agent/orchestrator.py` 파이프라인 |
| Tool / ReAct | MCP `rag_search`·`rag_ingest` 등 (`rag_agent/mcp_client.py`, `mcp_servers/`) |
| RAG (임베딩·Vector DB) | Chroma + MCP RAG 도구, 수집·검색 API (`rag_agent/api/`) |
| Structured Output / JSON 라우팅 | 오케스트레이터가 LLM JSON 한 덩어리로 `agent_id`·ID 필드 파싱 |
| FastAPI 백엔드 | `rag_agent/api/main.py` |
| UI | `frontend/` (Vite + React) |
| Docker(선택) | 루트 `Dockerfile`, 실행 예: `docker build -t aicrm-api .` 후 `docker run -p 8000:8000 --env-file .env aicrm-api` |
| 환경변수·API Key | `.env` / `rag_agent/config.py`, 예시는 `.env.example`, `docs/env/` |
| MCP | RAG DB MCP 서버 `mcp_servers/`, 클라이언트 호출로 도구 연동 |
| A2A 성격 | 오케스트레이터가 전문 에이전트를 선택·위임하는 구조 (`run_agent`) |

**참고:** 가이드는 “모든 기술을 다 쓰는 것”이 아니라 적절한 조합을 권장합니다. 여기서는 LangGraph로 **CRM 질의 파이프라인**을 명시적으로 그래프화해 필수 기술 요소를 충족합니다.
