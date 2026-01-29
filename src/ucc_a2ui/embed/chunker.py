from __future__ import annotations

from typing import Iterable, List, Tuple


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    if chunk_size <= 0:
        return [text]
    chunks: List[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        chunks.append(text[start:end])
        start = end - chunk_overlap if chunk_overlap > 0 else end
        if start < 0:
            start = 0
        if start >= length:
            break
    return chunks


def chunk_documents(texts: Iterable[str], chunk_size: int, chunk_overlap: int) -> List[str]:
    chunks: List[str] = []
    for text in texts:
        chunks.extend(chunk_text(text, chunk_size, chunk_overlap))
    return chunks


def chunk_documents_with_sources(
    documents: Iterable[Tuple[str, str]], chunk_size: int, chunk_overlap: int
) -> List[Tuple[str, str]]:
    chunks: List[Tuple[str, str]] = []
    for text, source in documents:
        for chunk in chunk_text(text, chunk_size, chunk_overlap):
            chunks.append((chunk, source))
    return chunks
