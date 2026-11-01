"""Text prep: normalises the text, splits syllables, finds repeated lines."""

from hymnstring.contracts import HymnText, PreparedText
from hymnstring.harness import Node, not_built

NODE = Node("text_prep", HymnText, PreparedText, not_built)
