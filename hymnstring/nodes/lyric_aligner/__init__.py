"""Lyric aligner: when each known syllable is sung."""

from hymnstring.contracts import AlignerInput, SyllableTimes
from hymnstring.harness import Node, not_built

NODE = Node("lyric_aligner", AlignerInput, SyllableTimes, not_built)
