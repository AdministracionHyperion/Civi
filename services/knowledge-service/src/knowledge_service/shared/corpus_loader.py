from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Any


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
TAG_SPLIT_RE = re.compile(r"[,\s]+")


@dataclass(frozen=True)
class CorpusChunk:
    id: str
    doc_id: str
    title: str
    domain: str
    tags: tuple[str, ...]
    body: str


def _parse_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    match = FRONTMATTER_RE.match(raw.strip())
    if not match:
        return {}, raw.strip()

    meta: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "tags":
            inner = value.strip("[]")
            tags = [part.strip().strip("'\"") for part in TAG_SPLIT_RE.split(inner) if part.strip().strip("'\"")]
            meta["tags"] = tags
        else:
            meta[key] = value.strip("'\"")
    return meta, match.group(2).strip()


def _chunk_body(body: str, *, max_chars: int = 700) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]
    if not paragraphs:
        return [body.strip()] if body.strip() else []

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(paragraph) <= max_chars:
            current = paragraph
        else:
            for start in range(0, len(paragraph), max_chars):
                chunks.append(paragraph[start : start + max_chars].strip())
            current = ""
    if current:
        chunks.append(current)
    return chunks


def _load_markdown_doc(name: str, raw: str) -> list[CorpusChunk]:
    meta, body = _parse_frontmatter(raw)
    doc_id = str(meta.get("id") or name.replace(".md", ""))
    title = str(meta.get("title") or doc_id)
    domain = str(meta.get("domain") or "general")
    tags = tuple(str(tag) for tag in (meta.get("tags") or []))
    chunks = _chunk_body(body)
    return [
        CorpusChunk(
            id=f"{doc_id}#{index}",
            doc_id=doc_id,
            title=title,
            domain=domain,
            tags=tags,
            body=chunk,
        )
        for index, chunk in enumerate(chunks, start=1)
    ]


@lru_cache(maxsize=1)
def load_corpus_chunks() -> tuple[CorpusChunk, ...]:
    root = files("knowledge_service.data").joinpath("corpus")
    chunks: list[CorpusChunk] = []
    for entry in sorted(root.iterdir()):
        name = entry.name
        if not name.endswith(".md"):
            continue
        raw = entry.read_text(encoding="utf-8")
        chunks.extend(_load_markdown_doc(name, raw))
    return tuple(chunks)
