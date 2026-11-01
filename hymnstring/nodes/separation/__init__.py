"""Separation: isolates the voice, or passes the full mix through when bypassed."""

from hymnstring.contracts import SeparationInput, Voice
from hymnstring.harness import Node, not_built

NODE = Node("separation", SeparationInput, Voice, not_built)
