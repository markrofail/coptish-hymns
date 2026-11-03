"""The synthesiser: sings a known string, so every audio part can be tested against exact answers.

It runs as a command, `python -m hymnstring.synth`, but it isn't a graph node, so it isn't in `nodes/`.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from hymnstring.contracts import GroundTruth, HymnString, SynthInput, SynthOutput, SynthSettings, Voice
from hymnstring.harness import ContractError, Node
from hymnstring.notation import parse_hymn
from hymnstring.synth.random_hymns import PlannedEvent, RandomHymn, random_hymn, random_settings
from hymnstring.synth.room import CYMBAL_HIT_S, echo_response, in_the_room
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
    """Sings the string and puts it in its room. The samples and the true values come from one score,
    so they can't disagree."""
    score = build_score(parse_hymn(string.text), settings)
    samples = in_the_room(sing(score, settings), score, settings)
    return Synthesis(samples, settings.sample_rate_hz, truth_of(score, settings))


def run(given: SynthInput) -> SynthOutput:
    """Sings the string, writes the recording to `out_path` and returns it with the true values. Nothing
    is made until the singing has worked, so a string that can't be sung leaves no folder behind."""
    try:
        sung = synthesise(given.string, given.settings)
    except SynthError as error:
        raise ContractError(f"synth: {error}") from error
    out = Path(given.out_path)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        write_wav(out, sung.samples, sung.sample_rate_hz)
    except OSError as error:
        raise ContractError(f"synth: cannot write out_path {given.out_path!r}: {error}") from error
    voice = Voice(
        path=given.out_path,
        sample_rate_hz=sung.sample_rate_hz,
        duration_s=len(sung.samples) / sung.sample_rate_hz,
        backend="bypass",  # separation is skipped, so the file is what the next nodes listen to
        accompaniment_path=None,
    )
    return SynthOutput(voice=voice, truth=sung.truth)


NODE = Node("synth", SynthInput, SynthOutput, run)


__all__ = [
    "CYMBALS",
    "CYMBAL_HIT_S",
    "ECHO",
    "MAX_SECONDS",
    "NODE",
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
    "echo_response",
    "in_the_room",
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
