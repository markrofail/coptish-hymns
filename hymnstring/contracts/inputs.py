"""Inputs for nodes with several incoming edges. A node takes one JSON document."""

from hymnstring.contracts.audio import (
    NoteStarts,
    PitchTrack,
    PulseUnit,
    Recording,
    SyllableTimes,
    Voice,
)
from hymnstring.contracts.base import Contract
from hymnstring.contracts.judgement import HymnString, LibraryEntry, Patterns, RoundTripReport
from hymnstring.contracts.text import PreparedText, Sounds


class AlignerInput(Contract):
    voice: Voice
    sounds: Sounds


class OnsetsInput(Contract):
    voice: Voice
    pitch_track: PitchTrack
    syllable_times: SyllableTimes


class MinerInput(Contract):
    text: PreparedText
    pitch_track: PitchTrack
    pulse_unit: PulseUnit
    note_starts: NoteStarts
    syllable_times: SyllableTimes
    library: LibraryEntry | None


class InterpreterInput(Contract):
    """last_try and last_report are filled in when the round-trip check sends a phrase back."""

    text: PreparedText
    sounds: Sounds
    pitch_track: PitchTrack
    pulse_unit: PulseUnit
    note_starts: NoteStarts
    syllable_times: SyllableTimes
    patterns: Patterns
    library: LibraryEntry | None
    last_try: HymnString | None
    last_report: RoundTripReport | None


class RoundTripInput(Contract):
    string: HymnString
    text: PreparedText
    pitch_track: PitchTrack
    pulse_unit: PulseUnit
    syllable_times: SyllableTimes


class RenderInput(Contract):
    """Only the string is required; the rest adds the audio sync and the check results."""

    string: HymnString
    report: RoundTripReport | None
    recording: Recording | None
    syllable_times: SyllableTimes | None
