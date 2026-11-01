"""Typed schemas for every edge in the graph."""

from hymnstring.contracts.audio import (
    NoteStarts,
    PitchTrack,
    PulseUnit,
    Recording,
    SyllableTimes,
    Voice,
)
from hymnstring.contracts.base import Contract, Empty
from hymnstring.contracts.inputs import (
    AlignerInput,
    InterpreterInput,
    MinerInput,
    OnsetsInput,
    RenderInput,
    RoundTripInput,
)
from hymnstring.contracts.judgement import (
    HymnString,
    LibraryEntry,
    Patterns,
    RenderedPage,
    ReviewRecord,
    RoundTripReport,
)
from hymnstring.contracts.text import HymnText, PreparedText, Sounds

__all__ = [
    "AlignerInput",
    "Contract",
    "Empty",
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
    "PulseUnit",
    "Recording",
    "RenderInput",
    "RenderedPage",
    "ReviewRecord",
    "RoundTripInput",
    "RoundTripReport",
    "Sounds",
    "SyllableTimes",
    "Voice",
]
