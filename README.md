# AI 영업관리 포탈

ChromaDB 기반 경량 RAG, MCP로 문서 DB 접근, 4개 전문 에이전트 + 오케스트레이터 구성.

## 문서 (PRD·개발표준)

- **PRD·기획**: `docs/prd/` — 샘플 `sample-prd.md`
- **개발표준(팀용 Markdown)**: `docs/standards/` — 샘플 `sample-development-standard.md`
- **Cursor/AI 규칙(.mdc)**: `standards/` 및 `.cursor/rules/` (자동 적용·glob용)

폴더 역할 요약은 `docs/README.md`를 참고하세요.

## 사전 요구

- Python 3.11+
- Node.js 20+ (프론트)

## 백엔드

```bash
cd rag-orchestrator-agent
python -m venv .venv
.venv\Scripts\activate
pip install -e .
uvicorn rag_agent.api.main:app --reload --host 127.0.0.1 --port 8000
```

## MCP 서버 단독 실행 (디버그)

```bash
python -m mcp_servers.rag_db
```

Cursor에 붙일 때는 `cursor-mcp-rag-db.example.json` 내용을 MCP 설정에 맞게 병합하세요 (`cwd`/`PYTHONPATH`는 로컬 경로로 조정).

## 프론트엔드

```bash
cd frontend
npm install
npm run dev
```

Vite 프록시가 `/api`를 `http://127.0.0.1:8000`으로 넘깁니다.

### 한 번에 실행 (Windows)

백엔드·프론트를 각각 새 창에서 띄웁니다.

- PowerShell: `.\scripts\start-dev.ps1` (실행 정책이 막으면 `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`)
- 프로젝트 루트에서: `.\start-app.ps1` (위와 동일)
- **경로에 한글이 있으면** 채팅/에이전트가 붙여 넣은 `Set-Location 'D:\...\과제\...'` 명령은 인코딩이 깨질 수 있습니다. 반드시 위 스크립트로 실행하세요.
- CMD: `scripts\start-dev.bat` 또는 루트의 `start-app.bat`

### GitHub 원격 저장소에 올리기

과제용 빈 저장소: [minkyujoo/aibootcamp_20260326](https://github.com/minkyujoo/aibootcamp_20260326).

프로젝트 루트(`rag-orchestrator-agent`)에서 PowerShell:

`powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\publish-to-github.ps1`

최초 `git push` 전에 GitHub 인증(PAT 또는 `gh auth login`)이 필요할 수 있습니다. `.env`, `.venv`, `node_modules` 등은 `.gitignore`에 있습니다.

#### 상위 폴더 이름을 영어로 바꾸기 (권장)

`...\20260325_AIbootcamp과제\...` 처럼 경로에 한글이 있으면, **Cursor에서 이 폴더를 연 상태로는 이동이 막힐 수 있으니** 먼저 워크스페이스를 닫은 뒤:

1. 탐색기에서 `rag-orchestrator-agent` 폴더로 이동합니다.
2. PowerShell에서 실행: `powershell -ExecutionPolicy Bypass -File .\scripts\move-assignment-folder-to-english.ps1`
3. 출력된 **새 경로**로 Cursor에서 `rag-orchestrator-agent` 를 다시 엽니다.

## API 요약

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/ingest` | MCP `rag_ingest` (`chunk_size`, `chunk_overlap` 선택) |
| POST | `/api/chat` | 오케스트레이션 일괄 JSON 응답 |
| POST | `/api/chat/stream` | SSE (`trace`, `hits`, `token`, `done`) |
| GET | `/api/stats` | MCP `rag_stats` |

## 환경 변수

Azure OpenAI(AOAI) 및 배포 이름은 **`docs/env/ai-models.md`** 와 **`docs/env/azure-openai.example.env`** 를 참고하세요. 프로젝트 루트 `.env` 는 `rag_agent/config.py` 에서 자동 로드됩니다(`python-dotenv`, 셸 변수가 우선).

| 변수 | 설명 |
|------|------|
| `AOAI_ENDPOINT`, `AOAI_API_KEY`, `AOAI_DEPLOY_*` | Azure OpenAI (우선). 상세는 `docs/env/ai-models.md` |
| `OPENAI_API_KEY` | AOAI 미설정 시 OpenAI 공식 API 폴백 |
| `OPENAI_BASE_URL` | 선택, 기본 OpenAI 호환 엔드포인트 |
| `CHROMA_PATH` | Chroma 저장 경로 (기본 `./data/chroma`) |
| `RAG_SEARCH_RERANK` | `true`(기본) / `false` — MCP 검색 후 한국어·영문 토큰 겹침 재순위 |
| `RAG_USE_AOAI_EMBEDDINGS` | `1`이면 Chroma가 AOAI 임베딩 사용 (`AOAI_*` 필요) |
| `CRM_REBUILD_SEED` | `1`/`true` — 다음 기동 시 고객사·사업기회·활동·추천 액션만 삭제 후 `rag_agent/crm/seed.py` 시드 재적용(영업담당 행은 유지). 새 DB는 자동 시드. |
| `AICRM_DB_PATH` | SQLite 경로 (기본 `data/aicrm.db`). 시드 갱신만 원하면 DB 파일 삭제 후 기동해도 됨. |

### RAG·MCP 스모크 테스트

```bash
python scripts/verify_rag_mcp.py
```
