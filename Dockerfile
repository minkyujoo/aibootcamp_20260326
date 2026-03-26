# 백엔드(FastAPI)만 컨테이너화. 프론트는 로컬 `npm run dev` 또는 별도 정적 호스팅.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY rag_agent ./rag_agent
COPY mcp_servers ./mcp_servers

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e .

EXPOSE 8000
CMD ["uvicorn", "rag_agent.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
