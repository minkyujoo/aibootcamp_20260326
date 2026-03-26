"""RAG DB MCP 서버(stdio) 호출 클라이언트."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from rag_agent.config import get_settings


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _python_executable() -> str:
    return sys.executable


async def call_mcp_tool(name: str, arguments: dict) -> str:
    """MCP 도구 호출 후 텍스트 결과 반환."""
    root = _project_root()
    settings = get_settings()
    params = StdioServerParameters(
        command=_python_executable(),
        args=["-m", settings.mcp_server_module],
        cwd=str(root),
        env={**os.environ, "PYTHONPATH": str(root)},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments)
            parts: list[str] = []
            for block in result.content:
                if hasattr(block, "text"):
                    parts.append(block.text)
            return "\n".join(parts) if parts else json.dumps(
                {"raw": str(result)}, ensure_ascii=False
            )


def call_mcp_tool_sync(name: str, arguments: dict) -> str:
    return asyncio.run(call_mcp_tool(name, arguments))
