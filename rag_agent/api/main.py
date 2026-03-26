import json
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from rag_agent.api.crm import router as crm_router
from rag_agent.crm.db import Base, engine
from rag_agent.crm.action_seed import ensure_action_items
from rag_agent.crm.seed import ensure_seed
from rag_agent.mcp_client import call_mcp_tool
from rag_agent.orchestrator import OrchestratorAgent


@asynccontextmanager
async def lifespan(app: FastAPI):
    import rag_agent.crm.models  # noqa: F401 — 메타데이터 등록

    Base.metadata.create_all(bind=engine)
    from rag_agent.crm.db import SessionLocal, ensure_sqlite_companies_dart_column

    ensure_sqlite_companies_dart_column()

    db = SessionLocal()
    try:
        ensure_seed(db)
        ensure_action_items(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="AI 영업관리 포탈",
    version="0.1.0",
    lifespan=lifespan,
    redirect_slashes=False,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_orch = OrchestratorAgent()

app.include_router(crm_router, prefix="/api/crm", tags=["aicrm"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None


class IngestRequest(BaseModel):
    text: str = Field(..., min_length=1)
    doc_id: str | None = None
    source: str = "api"
    chunk_size: int = Field(0, ge=0, le=50_000)
    chunk_overlap: int = Field(80, ge=0, le=5000)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat")
async def chat(body: ChatRequest) -> dict[str, Any]:
    sid = body.session_id or str(uuid.uuid4())
    try:
        return await _orch.run(body.message, sid)
    except Exception as e:  # noqa: BLE001 — 상위에서 사용자 메시지로 변환
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/chat/stream")
async def chat_stream(body: ChatRequest) -> StreamingResponse:
    sid = body.session_id or str(uuid.uuid4())

    async def event_gen():
        try:
            async for ev in _orch.run_stream(body.message, sid):
                e = ev["event"]
                d = ev["data"]
                line = json.dumps(d, ensure_ascii=False)
                yield f"event: {e}\ndata: {line}\n\n"
        except Exception as ex:  # noqa: BLE001
            err = json.dumps({"error": str(ex)}, ensure_ascii=False)
            yield f"event: error\ndata: {err}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/ingest")
async def ingest(body: IngestRequest) -> dict[str, Any]:
    try:
        raw = await call_mcp_tool(
            "rag_ingest",
            {
                "text": body.text,
                "doc_id": body.doc_id,
                "source": body.source,
                "chunk_size": body.chunk_size,
                "chunk_overlap": body.chunk_overlap,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


@app.get("/api/stats")
async def stats() -> dict[str, Any]:
    raw = await call_mcp_tool("rag_stats", {})
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}
