"""Build the knowledge base from the raw corpus and persist it to JSON.

Usage:
    python -m herb_hermes.index_build [corpus_dir] [out_path]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from .config import DEFAULT_CORPUS_DIR, KB_PATH
from .store import KnowledgeBase


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    corpus_dir = Path(argv[0]) if len(argv) > 0 else DEFAULT_CORPUS_DIR
    out_path = Path(argv[1]) if len(argv) > 1 else KB_PATH

    if not corpus_dir.exists():
        print(f"[error] corpus dir not found: {corpus_dir}", file=sys.stderr)
        return 1

    print(f"[build] loading corpus from {corpus_dir} …")
    t0 = time.time()
    kb = KnowledgeBase.build(corpus_dir)
    print(f"[build] built in {time.time() - t0:.1f}s")
    for k, v in kb.stats.items():
        print(f"        {k:18s} {v}")

    path = kb.save(out_path)
    size_mb = path.stat().st_size / 1e6
    print(f"[build] saved knowledge base -> {path} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
