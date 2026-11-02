"""The synthesiser: sings a known string, so every audio part can be tested against exact answers."""

from hymnstring.synth.score import (
    CYMBALS,
    ECHO,
    MAX_SECONDS,
    NOISE,
    TIMING,
    Rest,
    Score,
    SungNote,
    SynthError,
    TimedSection,
    build_score,
    sample_count,
)
from hymnstring.synth.truth import pitch_at, true_values, truth_of

__all__ = [
    "CYMBALS",
    "ECHO",
    "MAX_SECONDS",
    "NOISE",
    "Rest",
    "Score",
    "SungNote",
    "SynthError",
    "TIMING",
    "TimedSection",
    "build_score",
    "pitch_at",
    "sample_count",
    "true_values",
    "truth_of",
]
