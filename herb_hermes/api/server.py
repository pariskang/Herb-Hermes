"""FastAPI HTTP API for Herb-Hermes — the 'research cockpit' backend.

Run:
    pip install fastapi uvicorn
    python -m herb_hermes.index_build          # build the KB once
    uvicorn herb_hermes.api.server:app --reload

The knowledge base is loaded once at startup (or built on demand if absent).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException, Query
except Exception as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "FastAPI is required for the API layer. Install with: pip install fastapi uvicorn"
    ) from exc

from ..config import DEFAULT_CORPUS_DIR, KB_PATH
from ..discovery.hypothesis import build_hypothesis_card
from ..discovery.sourcing import trace_herb
from ..store import KnowledgeBase

app = FastAPI(
    title="Herb-Hermes API",
    version="0.1.0",
    description="本草—方剂—机制—发现 证据操作系统 (MVP)",
)


@lru_cache(maxsize=1)
def get_kb() -> KnowledgeBase:
    if KB_PATH.exists():
        return KnowledgeBase.load(KB_PATH)
    kb = KnowledgeBase.build(DEFAULT_CORPUS_DIR)
    kb.save()
    return kb


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": app.version}


@app.get("/stats")
def stats() -> dict:
    return get_kb().stats


@app.get("/herb/{name}")
def herb(name: str) -> dict:
    kb = get_kb()
    norm = kb.normalizer.normalize(name)
    entries = kb.get_entries(name)
    return {
        "query": name,
        "canonical": norm.canonical,
        "aliases": norm.aliases,
        "ambiguous": norm.ambiguous,
        "ambiguity_note": norm.note,
        "entries": [e.to_dict() for e in entries],
        "graph_neighbors": kb.graph.neighbors(norm.canonical),
    }


@app.get("/trace/{name}")
def trace(name: str, limit: int = Query(40, ge=1, le=200)) -> dict:
    res = trace_herb(get_kb(), name, max_evidence=limit)
    return res.to_dict()


@app.get("/search")
def search(q: str, limit: int = Query(10, ge=1, le=50)) -> dict:
    hits = get_kb().bm25.search(q, top_k=limit)
    return {
        "query": q,
        "results": [
            {"score": round(s, 3), "citation": p.citation, "book": p.book_title,
             "section": p.section, "snippet": p.text.strip()[:200]}
            for p, s in hits
        ],
    }


@app.get("/pairs")
def pairs(herb: Optional[str] = None, limit: int = Query(30, ge=1, le=200)) -> dict:
    kb = get_kb()
    res = kb.pairs_for(herb, top_k=limit) if herb else kb.pairs[:limit]
    return {"herb": herb, "pairs": [p.to_dict() for p in res]}


@app.get("/hypothesis")
def hypothesis(herb: str, partner: Optional[str] = None, disease: str = "骨质疏松") -> dict:
    card = build_hypothesis_card(get_kb(), herb, partner=partner, disease=disease)
    return card.to_dict()


@app.get("/graph/{name}")
def graph(name: str) -> dict:
    kb = get_kb()
    canonical = kb.normalizer.normalize(name).canonical
    return {"herb": canonical, "neighbors": kb.graph.neighbors(canonical)}
