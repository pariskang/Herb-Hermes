"""Project paths and tunable constants."""

from __future__ import annotations

import os
from pathlib import Path

# Repository root = parent of this package directory.
PACKAGE_DIR = Path(__file__).resolve().parent
ROOT_DIR = PACKAGE_DIR.parent

DATA_DIR = Path(os.environ.get("HERB_HERMES_DATA", ROOT_DIR / "data"))
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

# Default corpus location: the 本草 (materia medica) category bundle.
DEFAULT_CORPUS_DIR = RAW_DIR / "本草"

# Where the built knowledge base is stored.
KB_PATH = PROCESSED_DIR / "herb_hermes_kb.json"

# Retrieval defaults.
BM25_K1 = 1.5
BM25_B = 0.75

# Co-occurrence mining defaults.
MIN_PAIR_COUNT = 3
