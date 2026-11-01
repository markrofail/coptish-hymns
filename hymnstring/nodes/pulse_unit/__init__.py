"""Pulse unit: the size of the half note, per section."""

from hymnstring.contracts import PulseInput, PulseUnit
from hymnstring.harness import Node, not_built

NODE = Node("pulse_unit", PulseInput, PulseUnit, not_built)
