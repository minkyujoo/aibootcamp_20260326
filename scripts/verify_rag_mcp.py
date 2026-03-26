#!/usr/bin/env python3
"""RAG stdio MCP(rag_ingest/search/stats) 및 FastAPI(/api/ingest, /api/stats, /api/health) 검증.

임시 CHROMA_PATH·AICRM_DB_PATH 를 쓰므로 기존 로컬 데이터를 건드리지 않습니다.
기본은 Chroma 내장 임베딩입니다. AOAI 임베딩을 쓰려면 실행 전 셸에 RAG_USE_AOAI_EMBEDDINGS=1 과 AOAI_* 를 설정하세요.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


def _bootstrap_env() -> None:
    root = Path(__file__).resolve().parent.parent
    os.environ.setdefault("PYTHONPATH", str(root))
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    td = Path(tempfile.mkdtemp(prefix="rag_mcp_verify_"))
    os.environ["CHROMA_PATH"] = str(td / "chroma")
    os.environ["AICRM_DB_PATH"] = str(td / "aicrm.db")
    # 검증 재현성: 사용자 셸에 켜져 있어도 기본 임베딩으로 MCP만 검증
    os.environ.pop("RAG_USE_AOAI_EMBEDDINGS", None)


def main() -> int:
    _bootstrap_env()
    print(f"[verify] CHROMA_PATH={os.environ['CHROMA_PATH']}")
    print(f"[verify] AICRM_DB_PATH={os.environ['AICRM_DB_PATH']}")

    from rag_agent.mcp_client import call_mcp_tool_sync

    raw = call_mcp_tool_sync(
        "rag_ingest",
        {
            "text": "MCP 직접 호출 검증 문서. 키워드: 부트캠프 RAG.",
            "source": "mcp_verify",
        },
    )
    print("[1] mcp rag_ingest:", raw)
    d1 = json.loads(raw)
    assert d1.get("ok") is True, d1

    raw2 = call_mcp_tool_sync("rag_search", {"query": "부트캠프", "n_results": 3})
    tail = "..." if len(raw2) > 400 else ""
    print("[2] mcp rag_search:", raw2[:400], tail, sep="")
    hits = json.loads(raw2)
    assert len(hits) >= 1

    raw3 = call_mcp_tool_sync("rag_stats", {})
    print("[3] mcp rag_stats:", raw3)
    assert json.loads(raw3).get("count", 0) >= 1

    from fastapi.testclient import TestClient
    from rag_agent.api.main import app

    with TestClient(app) as client:
        r = client.post(
            "/api/ingest",
            json={
                "text": "FastAPI 경유 MCP 인제스트 검증. 키워드: 오케스트레이터.",
                "source": "api_verify",
            },
        )
        print("[4] POST /api/ingest", r.status_code, r.text[:300])
        assert r.status_code == 200, r.text
        ing = r.json()
        assert ing.get("ok") is True, ing

        s = client.get("/api/stats")
        print("[5] GET /api/stats", s.status_code, s.text)
        assert s.status_code == 200
        st = s.json()
        assert isinstance(st, dict) and st.get("count", 0) >= 2

        h = client.get("/api/health")
        assert h.status_code == 200
        assert h.json().get("status") == "ok"

    print("[verify] OK - RAG+MCP+API(ingest/stats/health)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
