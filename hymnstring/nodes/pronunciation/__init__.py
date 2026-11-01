"""Pronunciation: the sounds sung for each syllable."""

from hymnstring.contracts import PreparedText, Sounds
from hymnstring.harness import Node, not_built

NODE = Node("pronunciation", PreparedText, Sounds, not_built)
