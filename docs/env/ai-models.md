# AI 모델 환경 변수 (Azure OpenAI 통합)

애플리케이션은 **Azure OpenAI(AOAI)** 를 우선 사용하고, 설정이 없을 때만 **OpenAI 공식 API** (`OPENAI_API_KEY`) 로 폴백합니다.

## Azure OpenAI (권장)

| 변수 | 설명 |
|------|------|
| `AOAI_ENDPOINT` | 리소스 엔드포인트 URL (팀 예시: `https://skcc-atl-dev-openai-01.openai.azure.com/`) |
| `AOAI_API_KEY` | Azure 포털에서 발급한 키 (**비밀 — Git에 커밋하지 마세요**) |
| `AOAI_API_VERSION` | REST API 버전 (기본값: `2024-08-01-preview`) |
| `AOAI_DEPLOY_GPT4O_MINI` | 채팅용 배포 이름 (기본 LLM, Query Planner·Synthesis·CRM 에이전트) |
| `AOAI_DEPLOY_GPT4O` | 고성능 채팅 배포 이름 (`AOAI_CHAT_DEPLOY=gpt4o` 일 때 사용) |
| `AOAI_DEPLOY_EMBED_3_LARGE` | 임베딩 배포 (참고·향후 확장) |
| `AOAI_DEPLOY_EMBED_3_SMALL` | RAG Chroma 기본 임베딩 배포 (`RAG_USE_AOAI_EMBEDDINGS=1` 시) |
| `AOAI_DEPLOY_EMBED_ADA` | ada 임베딩 배포 (참고) |

### 채팅 모델 선택

| 변수 | 설명 |
|------|------|
| `AOAI_CHAT_DEPLOY` | `mini`(기본) 또는 `gpt4o` — 각각 `AOAI_DEPLOY_GPT4O_MINI` / `AOAI_DEPLOY_GPT4O` 배포를 사용합니다. |

### RAG 임베딩 (Chroma)

| 변수 | 설명 |
|------|------|
| `RAG_USE_AOAI_EMBEDDINGS` | `1`이면 AOAI 임베딩 함수로 `rag_docs` 컬렉션을 생성·조회합니다. **기존 로컬 임베딩과 벡터 공간이 달라 호환이 깨질 수 있으므로**, 전환 시 `CHROMA_PATH` 를 새 디렉터리로 두거나 데이터를 재인제스트하세요. |

## OpenAI 공식 API (폴백)

`AOAI_ENDPOINT` 와 `AOAI_API_KEY` 가 **둘 다** 없을 때만 사용됩니다.

| 변수 | 설명 |
|------|------|
| `OPENAI_API_KEY` | OpenAI API 키 |
| `OPENAI_BASE_URL` | 선택, 프록시/호환 엔드포인트 |
| `OPENAI_MODEL` | 채팅 모델 이름 (기본 `gpt-4o-mini`) |

## 로컬 설정 방법

1. 이 폴더의 `azure-openai.example.env` 를 참고해 프로젝트 루트에 `.env` 를 만듭니다. (`AOAI_API_KEY` 만 로컬에 채웁니다. **키는 Git에 커밋하지 마세요.**)
2. 앱은 `python-dotenv` 로 프로젝트 루트 `.env` 를 자동 로드합니다(이미 셸에 있는 변수는 덮어쓰지 않음).
3. 백엔드는 **포트 8000** 을 권장합니다(Vite 프록시 기본값과 동일).

```bash
uvicorn rag_agent.api.main:app --reload --host 127.0.0.1 --port 8000
```

### RAG + MCP 동작 검증

임시 `CHROMA_PATH` / `AICRM_DB_PATH` 로 **stdio MCP** 와 **FastAPI → MCP** 경로를 한 번에 확인합니다.

```bash
python scripts/verify_rag_mcp.py
```

`RAG_USE_AOAI_EMBEDDINGS=1` 로 AOAI 임베딩을 쓰는 경우, 위 스크립트 실행 전에 `AOAI_*` 가 설정되어 있어야 하며, 임베딩 전환 시 기존 Chroma 데이터와 호환되지 않을 수 있습니다.

코드는 `rag_agent/config.py` 에서 위 변수를 읽고, 채팅 호출은 `rag_agent/llm_client.py` 를 통해 **Azure / OpenAI 를 동일 인터페이스**로 사용합니다.
