"""Pitch contour: pitch every 10 ms, plus vibrato."""

from hymnstring.contracts import PitchTrack, Voice
from hymnstring.harness import Node, not_built

NODE = Node("pitch_contour", Voice, PitchTrack, not_built)
