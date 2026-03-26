"""문자 단위 청크 분할 (UTF-8 안전, 줄바꿈·공백 우선 경계)."""

from __future__ import annotations


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if chunk_size <= 0:
        return [text]
    overlap = max(0, min(overlap, chunk_size - 1))
    t = text.strip()
    if not t:
        return []
    chunks: list[str] = []
    start = 0
    n = len(t)
    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            window = t[start:end]
            br = window.rfind("\n")
            sp = window.rfind(" ")
            break_at = max(br, sp)
            if break_at > chunk_size // 3:
                end = start + break_at + 1
        piece = t[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        next_start = end - overlap
        if next_start <= start:
            next_start = end
        start = next_start
    return chunks
