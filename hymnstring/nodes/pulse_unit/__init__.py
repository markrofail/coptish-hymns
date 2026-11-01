"""Pulse unit: the size of the half note."""

from hymnstring.contracts import PulseUnit, Voice
from hymnstring.harness import Node, not_built

NODE = Node("pulse_unit", Voice, PulseUnit, not_built)
