"""Herb-name normalization: aliases, simplified/traditional bridging, ambiguity."""

from .normalizer import HerbNormalizer
from .aliases import ALIAS_TABLE, AMBIGUOUS_TOKENS

__all__ = ["HerbNormalizer", "ALIAS_TABLE", "AMBIGUOUS_TOKENS"]
