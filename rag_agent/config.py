import os
from dataclasses import dataclass
from pathlib import Path


def _try_load_dotenv() -> None:
    """루트 `.env` → `docs/env/azure-openai.env` → `docs/env/azure-openai.example.env` 순으로 로드합니다.
    `override=False` 이므로 앞선 파일·이미 설정된 환경변수가 우선합니다."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    root = Path(__file__).resolve().parent.parent
    for rel in (
        ".env",
        "docs/env/azure-openai.env",
        "docs/env/azure-openai.example.env",
    ):
        p = root / rel
        if p.is_file():
            load_dotenv(p, override=False)


def _env_bool(key: str, default: bool) -> bool:
    v = os.environ.get(key)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    """애플리케이션 설정. AI 모델 변수 정의는 docs/env/ai-models.md 참고."""

    # Azure OpenAI (우선)
    aoai_endpoint: str | None
    aoai_api_key: str | None
    aoai_api_version: str
    aoai_deploy_gpt4o_mini: str
    aoai_deploy_gpt4o: str
    aoai_deploy_embed_3_large: str
    aoai_deploy_embed_3_small: str
    aoai_deploy_embed_ada: str
    aoai_chat_deploy: str
    # OpenAI 공식 API (AOAI 미설정 시 폴백)
    openai_api_key: str | None
    openai_base_url: str | None
    openai_model: str
    # 기타
    chroma_path: Path
    mcp_server_module: str
    rag_search_rerank: bool
    rag_use_aoai_embeddings: bool

    def use_azure_openai(self) -> bool:
        ep = (self.aoai_endpoint or "").strip()
        key = (self.aoai_api_key or "").strip()
        return bool(ep and key)

    def resolved_aoai_chat_deployment(self) -> str:
        p = (self.aoai_chat_deploy or "mini").strip().lower()
        if p in ("gpt4o", "gpt-4o", "4o"):
            return self.aoai_deploy_gpt4o
        return self.aoai_deploy_gpt4o_mini

    @classmethod
    def load(cls) -> "Settings":
        _try_load_dotenv()
        chroma = os.environ.get("CHROMA_PATH", "./data/chroma")
        return cls(
            aoai_endpoint=os.environ.get("AOAI_ENDPOINT"),
            aoai_api_key=os.environ.get("AOAI_API_KEY"),
            aoai_api_version=os.environ.get("AOAI_API_VERSION", "2024-08-01-preview"),
            aoai_deploy_gpt4o_mini=os.environ.get("AOAI_DEPLOY_GPT4O_MINI", "gpt-4o-mini"),
            aoai_deploy_gpt4o=os.environ.get("AOAI_DEPLOY_GPT4O", "gpt-4o"),
            aoai_deploy_embed_3_large=os.environ.get(
                "AOAI_DEPLOY_EMBED_3_LARGE", "text-embedding-3-large"
            ),
            aoai_deploy_embed_3_small=os.environ.get(
                "AOAI_DEPLOY_EMBED_3_SMALL", "text-embedding-3-small"
            ),
            aoai_deploy_embed_ada=os.environ.get(
                "AOAI_DEPLOY_EMBED_ADA", "text-embedding-ada-002"
            ),
            aoai_chat_deploy=os.environ.get("AOAI_CHAT_DEPLOY", "mini"),
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
            openai_base_url=os.environ.get("OPENAI_BASE_URL"),
            openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            chroma_path=Path(chroma),
            mcp_server_module=os.environ.get("MCP_RAG_MODULE", "mcp_servers.rag_db"),
            rag_search_rerank=_env_bool("RAG_SEARCH_RERANK", True),
            rag_use_aoai_embeddings=_env_bool("RAG_USE_AOAI_EMBEDDINGS", False),
        )


def get_settings() -> Settings:
    return Settings.load()
