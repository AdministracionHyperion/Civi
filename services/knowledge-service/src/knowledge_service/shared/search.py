from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from knowledge_service.shared.corpus_loader import CorpusChunk, load_corpus_chunks


STOPWORDS = {
    "a",
    "al",
    "con",
    "de",
    "del",
    "el",
    "en",
    "es",
    "la",
    "las",
    "lo",
    "los",
    "me",
    "mi",
    "no",
    "o",
    "para",
    "por",
    "que",
    "se",
    "si",
    "un",
    "una",
    "y",
}


@dataclass(frozen=True)
class SearchHit:
    id: str
    title: str
    body: str
    domain: str
    score: float


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    ascii_text = ascii_text.lower()
    ascii_text = re.sub(r"[^a-z0-9\s]", " ", ascii_text)
    return re.sub(r"\s+", " ", ascii_text).strip()


def tokenize(value: str) -> list[str]:
    return [token for token in normalize_text(value).split() if token and token not in STOPWORDS and len(token) > 1]


def search_corpus(*, query: str, domain: str | None = None, limit: int = 5) -> list[SearchHit]:
    tokens = tokenize(query)
    if not tokens:
        return []

    active_domain = normalize_text(domain or "").replace(" ", "_") or None
    hits: list[SearchHit] = []
    for chunk in load_corpus_chunks():
        if active_domain and normalize_text(chunk.domain) != active_domain:
            continue
        score = _score_chunk(tokens, chunk)
        if score >= 0.18:
            hits.append(
                SearchHit(
                    id=chunk.id,
                    title=chunk.title,
                    body=chunk.body,
                    domain=chunk.domain,
                    score=round(score, 4),
                )
            )

    hits.sort(key=lambda item: (-item.score, item.id))
    return hits[: max(1, min(limit, 10))]


def _score_chunk(tokens: list[str], chunk: CorpusChunk) -> float:
    haystack = normalize_text(" ".join([chunk.title, chunk.body, " ".join(chunk.tags), chunk.domain]))
    hay_tokens = set(tokenize(haystack))
    if not hay_tokens:
        return 0.0

    overlap = sum(1 for token in tokens if token in hay_tokens)
    coverage = overlap / len(tokens)
    density = overlap / max(len(hay_tokens), 1)

    phrase_boost = 0.0
    joined = " ".join(tokens)
    if joined and joined in haystack:
        phrase_boost = 0.25

    tag_boost = 0.0
    tag_text = normalize_text(" ".join(chunk.tags))
    if any(token in tag_text for token in tokens):
        tag_boost = 0.12

    title_boost = 0.0
    title_norm = normalize_text(chunk.title)
    if any(token in title_norm for token in tokens):
        title_boost = 0.08

    return min(1.0, (coverage * 0.7) + (density * 0.2) + phrase_boost + tag_boost + title_boost)
