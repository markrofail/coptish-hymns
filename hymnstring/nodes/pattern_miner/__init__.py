"""Pattern miner: repeats and known motifs."""

from hymnstring.contracts import MinerInput, Patterns
from hymnstring.harness import Node, not_built

NODE = Node("pattern_miner", MinerInput, Patterns, not_built)
