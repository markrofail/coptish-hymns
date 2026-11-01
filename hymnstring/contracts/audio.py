"""The audio side: measurements of the recording, never quantised to a scale."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from hymnstring.contracts.base import (
    Contract,
    Index,
    NonEmpty,
    Positive,
    Score,
    Seconds,
    TimeSpan,
    require_counting_up,
    require_in_time_order,
)

SeparationBackend = Literal["bypass", "demucs", "roformer"]


class Recording(Contract):
    path: NonEmpty


class Voice(Contract):
    """What later nodes listen to. When bypassed, `path` is the full mix.

    A separation backend also keeps the accompaniment stem, for cymbal hits.
    """

    path: NonEmpty
    sample_rate_hz: Annotated[int, Field(gt=0)]
    duration_s: Positive
    backend: SeparationBackend
    accompaniment_path: NonEmpty | None

    @model_validator(mode="after")
    def only_separation_leaves_an_accompaniment(self) -> Self:
        if (self.backend == "bypass") != (self.accompaniment_path is None):
            raise ValueError("a separation backend keeps an accompaniment; bypass has none")
        return self


class Vibrato(TimeSpan):
    rate_hz: Positive
    width_cents: Positive


class PitchTrack(Contract):
    """One value per frame; f0 is null where the voice is silent."""

    hop_s: Positive
    f0_hz: tuple[Positive | None, ...]
    confidence: tuple[Score, ...]
    vibrato: tuple[Vibrato, ...]

    @model_validator(mode="after")
    def one_confidence_per_frame(self) -> Self:
        if len(self.f0_hz) != len(self.confidence):
            raise ValueError("f0_hz and confidence must have the same length")
        return self


class PulseSection(TimeSpan):
    half_note_s: Positive
    confidence: Score


class PulseUnit(Contract):
    """Lengths are relative within a hymn or a part of it, so each part has its own unit.

    One section by default, split at verse boundaries or long pauses.
    """

    source: Literal["note_durations", "cymbals"]
    sections: tuple[PulseSection, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def sections_do_not_overlap(self) -> Self:
        require_in_time_order(self.sections, "sections")
        return self


class StepSection(TimeSpan):
    """step_cents is null when a section has no stable intervals to measure."""

    step_cents: Positive | None
    confidence: Score


class StepSize(Contract):
    """How big one level is, measured per pulse section. Never a scale degree."""

    sections: tuple[StepSection, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def sections_do_not_overlap(self) -> Self:
        require_in_time_order(self.sections, "sections")
        return self


class SyllableTime(TimeSpan):
    syllable_index: Index
    confidence: Score


class SyllableTimes(Contract):
    """catch_all holds the audio that isn't in the text."""

    syllables: tuple[SyllableTime, ...]
    catch_all: tuple[TimeSpan, ...]

    @model_validator(mode="after")
    def syllables_in_order(self) -> Self:
        require_counting_up([time.syllable_index for time in self.syllables], "syllable indices")
        require_in_time_order(self.syllables, "syllables")
        return self


class NoteStart(Contract):
    start_s: Seconds
    syllable_index: Index
    cause: Literal["syllable_start", "pitch_change", "resung"]
    confidence: Score


class NoteStarts(Contract):
    notes: tuple[NoteStart, ...]
    breaths: tuple[TimeSpan, ...]

    @model_validator(mode="after")
    def notes_in_order(self) -> Self:
        for earlier, later in zip(self.notes, self.notes[1:]):
            if later.start_s <= earlier.start_s:
                raise ValueError("notes must be in time order")
        return self
