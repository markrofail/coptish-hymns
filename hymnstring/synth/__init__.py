"""The synthesiser: sings a known string, so every audio part can be tested against exact answers."""

from dataclasses import dataclass

import numpy as np

from hymnstring.contracts import GroundTruth, HymnString, SynthSettings
from hymnstring.notation import parse_hymn
from hymnstring.synth.random_hymns import PlannedEvent, RandomHymn, random_hymn, random_settings
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
from hymnstring.synth.voice import sing, write_wav


@dataclass(frozen=True)
class Synthesis:
    """A sung string: its samples, their rate, and the true values they should be measured against."""

    samples: np.ndarray
    sample_rate_hz: int
    truth: GroundTruth


def synthesise(string: HymnString, settings: SynthSettings) -> Synthesis:
    """Sings the string. The samples and the true values come from one score, so they can't disagree."""
    score = build_score(parse_hymn(string.text), settings)
    return Synthesis(sing(score, settings), settings.sample_rate_hz, truth_of(score, settings))


__all__ = [
    "CYMBALS",
    "ECHO",
    "MAX_SECONDS",
    "NOISE",
    "PlannedEvent",
    "RandomHymn",
    "Rest",
    "Score",
    "SungNote",
    "SynthError",
    "Synthesis",
    "TIMING",
    "TimedSection",
    "build_score",
    "pitch_at",
    "random_hymn",
    "random_settings",
    "sample_count",
    "sing",
    "synthesise",
    "true_values",
    "truth_of",
    "write_wav",
]
