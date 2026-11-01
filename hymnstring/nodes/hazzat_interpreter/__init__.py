"""Hazzat interpreter: makes the cantor-like calls and writes the string."""

from hymnstring.contracts import HymnString, InterpreterInput
from hymnstring.harness import Node, not_built

NODE = Node("hazzat_interpreter", InterpreterInput, HymnString, not_built)
