"""
ChromaDB 기반 RAG 저장소 MCP 서버.
환경변수 CHROMA_PATH 로 영속 경로 지정 (기본 ./data/chroma).
"""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path

import chromadb
from mcp.server.fastmcp import FastMCP

from mcp_servers.rag_db.chunking import chunk_text

mcp = FastMCP("rag-db")


def _chroma_dir() -> str:
    raw = os.environ.get("CHROMA_PATH", "./data/chroma")
    path = Path(raw).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def _aoai_embedding_enabled() -> bool:
    v = os.environ.get("RAG_USE_AOAI_EMBEDDINGS", "")
    return v.strip().lower() in ("1", "true", "yes", "on")


def _collection():
    client = chromadb.PersistentClient(path=_chroma_dir())
    meta = {"hnsw:space": "cosine"}
    if _aoai_embedding_enabled():
        ep = (os.environ.get("AOAI_ENDPOINT") or "").strip().rstrip("/")
        key = (os.environ.get("AOAI_API_KEY") or "").strip()
        if not ep or not key:
            raise RuntimeError(
                "RAG_USE_AOAI_EMBEDDINGS=1 인 경우 AOAI_ENDPOINT 와 AOAI_API_KEY 가 필요합니다. "
                "docs/env/ai-models.md 참고."
            )
        deploy = os.environ.get("AOAI_DEPLOY_EMBED_3_SMALL", "text-embedding-3-small")
        api_ver = os.environ.get("AOAI_API_VERSION", "2024-08-01-preview")
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

        ef = OpenAIEmbeddingFunction(
            model_name=deploy,
            api_base=ep,
            api_type="azure",
            api_version=api_ver,
            deployment_id=deploy,
            api_key=key,
            api_key_env_var="AOAI_API_KEY",
        )
        return client.get_or_create_collection(
            name="rag_docs",
            embedding_function=ef,
            metadata=meta,
        )
    return client.get_or_create_collection(name="rag_docs", metadata=meta)


def _tokenize(s: str) -> set[str]:
    return set(re.findall(r"[\w가-힣]+", s.lower()))


def _lexical_rerank(query: str, hits: list[dict], top_k: int) -> list[dict]:
    qtok = _tokenize(query)
    if not qtok:
        return hits[:top_k]

    def key(h: dict) -> tuple[int, float]:
        doc = (h.get("document") or "").lower()
        overlap = len(qtok & _tokenize(doc))
        dist = h.get("distance")
        if isinstance(dist, (int, float)):
            return (overlap, -float(dist))
        return (overlap, 0.0)

    ranked = sorted(hits, key=key, reverse=True)
    return ranked[:top_k]


@mcp.tool()
def rag_ingest(
    text: str,
    doc_id: str | None = None,
    source: str = "manual",
    chunk_size: int = 0,
    chunk_overlap: int = 80,
) -> str:
    """문서를 벡터 DB에 추가합니다. chunk_size>0 이면 문자 단위로 분할해 여러 임베딩을 저장합니다."""
    col = _collection()
    parent = doc_id or str(uuid.uuid4())
    if chunk_size and chunk_size > 0:
        parts = chunk_text(text, chunk_size, chunk_overlap)
        if not parts:
            return json.dumps({"ok": False, "error": "empty_text"}, ensure_ascii=False)
        ids: list[str] = []
        docs: list[str] = []
        metas: list[dict] = []
        for i, p in enumerate(parts):
            cid = f"{parent}::c{i}"
            ids.append(cid)
            docs.append(p)
            metas.append(
                {
                    "source": source,
                    "parent_doc_id": parent,
                    "chunk_index": i,
                }
            )
        col.add(ids=ids, documents=docs, metadatas=metas)
        return json.dumps(
            {"ok": True, "parent_id": parent, "chunks": len(parts)},
            ensure_ascii=False,
        )

    col.add(
        ids=[parent],
        documents=[text],
        metadatas=[{"source": source, "parent_doc_id": parent, "chunk_index": 0}],
    )
    return json.dumps({"ok": True, "id": parent, "chunks": 1}, ensure_ascii=False)


@mcp.tool()
def rag_search(query: str, n_results: int = 5, rerank: bool = False) -> str:
    """쿼리와 유사한 문서를 검색합니다. rerank=True 이면 후보를 넓게 가져온 뒤 한국어·영문 토큰 겹침으로 재정렬합니다."""
    col = _collection()
    n = max(1, min(int(n_results), 20))
    fetch_n = min(max(n * 3, n), 40) if rerank else n
    res = col.query(query_texts=[query], n_results=fetch_n)
    hits: list[dict] = []
    ids = res.get("ids") or [[]]
    docs = res.get("documents") or [[]]
    metas = res.get("metadatas") or [[]]
    dists = res.get("distances") or [[]]
    row_ids = ids[0] if ids else []
    for i, rid in enumerate(row_ids):
        meta = metas[0][i] if metas and metas[0] else {}
        hits.append(
            {
                "id": rid,
                "document": docs[0][i] if docs and docs[0] else "",
                "metadata": meta or {},
                "distance": dists[0][i] if dists and dists[0] else None,
            }
        )
    if rerank:
        hits = _lexical_rerank(query, hits, n)
    return json.dumps(hits, ensure_ascii=False)


@mcp.tool()
def rag_stats() -> str:
    """컬렉션 문서 수를 반환합니다."""
    col = _collection()
    return json.dumps({"count": col.count()}, ensure_ascii=False)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
