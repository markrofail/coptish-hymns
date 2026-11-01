"""Separation: isolates the voice."""

from hymnstring.contracts import Recording, Voice
from hymnstring.harness import Node, not_built

NODE = Node("separation", Recording, Voice, not_built)
