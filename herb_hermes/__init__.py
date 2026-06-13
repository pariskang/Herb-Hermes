"""Herb-Hermes: 本草—方剂—机制—发现 证据操作系统 (MVP core).

This package implements a runnable minimum-viable slice of the Herb-Hermes
design: classical materia-medica (本草) corpus ingestion, herb-name
normalization, a herb knowledge base, citation-tracked retrieval, a herb
knowledge graph, herb-pair (药对) co-occurrence mining, classical-source
tracing (本草溯源), and templated research-hypothesis cards.

Everything in the core runs on the Python standard library so the pipeline
works offline. The optional HTTP API layer uses FastAPI when installed.
"""

from .models import (
    BookMeta,
    Passage,
    HerbEntry,
    Evidence,
    SourcingResult,
    HerbPair,
    HypothesisCard,
)

__version__ = "0.1.0"

__all__ = [
    "BookMeta",
    "Passage",
    "HerbEntry",
    "Evidence",
    "SourcingResult",
    "HerbPair",
    "HypothesisCard",
    "__version__",
]
