"""Discovery layer: sourcing (溯源), pair mining (药对), hypothesis cards."""

from .sourcing import trace_herb
from .cooccurrence import mine_pairs, pairs_for_herb
from .hypothesis import build_hypothesis_card

__all__ = ["trace_herb", "mine_pairs", "pairs_for_herb", "build_hypothesis_card"]
