"""Typed schemas for every edge in the graph."""

from hymnstring.contracts.audio import (
    NoteStarts,
    PitchTrack,
    PulseUnit,
    Recording,
    StepSize,
    SyllableTimes,
    Voice,
)
from hymnstring.contracts.base import Contract, Empty
from hymnstring.contracts.inputs import (
    AlignerInput,
    InterpreterInput,
    MinerInput,
    OnsetsInput,
    PulseInput,
    RenderInput,
    RoundTripInput,
    SeparationInput,
    StepInput,
)
from hymnstring.contracts.judgement import (
    HymnString,
    LibraryEntry,
    Patterns,
    RenderedPage,
    ReviewRecord,
    RoundTripReport,
)
from hymnstring.contracts.synth import GroundTruth, SynthInput, SynthOutput, SynthSettings
from hymnstring.contracts.text import HymnText, PreparedText, Sounds

__all__ = [
    "AlignerInput",
    "Contract",
    "Empty",
    "GroundTruth",
    "HymnString",
    "HymnText",
    "InterpreterInput",
    "LibraryEntry",
    "MinerInput",
    "NoteStarts",
    "OnsetsInput",
    "Patterns",
    "PitchTrack",
    "PreparedText",
    "PulseInput",
    "PulseUnit",
    "Recording",
    "RenderInput",
    "RenderedPage",
    "ReviewRecord",
    "RoundTripInput",
    "RoundTripReport",
    "SeparationInput",
    "Sounds",
    "StepInput",
    "StepSize",
    "SyllableTimes",
    "SynthInput",
    "SynthOutput",
    "SynthSettings",
    "Voice",
]
