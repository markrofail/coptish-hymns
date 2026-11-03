"""The synthesiser's edges: what it is asked to sing, and the exact answers that come back with the audio."""

from typing import Annotated, Self

from pydantic import Field, model_validator

from hymnstring.contracts.audio import NoteStarts, PitchTrack, PulseUnit, StepSize, SyllableTimes, Voice
from hymnstring.contracts.base import Contract, Index, NonEmpty, Positive
from hymnstring.contracts.judgement import HymnString


class SynthSection(Contract):
    """Tempo and step from `first_phrase` until the next section starts."""

    first_phrase: Index
    half_note_s: Annotated[float, Field(ge=0.01)]  # seconds per half-note unit
    step_cents: Annotated[float, Field(gt=0, le=2400)]  # the size of one level


class SynthSettings(Contract):
    """How a string is sung and recorded. The default is a clean tone: steady timing and pitch, and
    no noise, echo or cymbals. Tempo and step have no default, so a run always says what it means."""

    seed: Index
    sections: tuple[SynthSection, ...] = Field(min_length=1)
    base_hz: Positive = 130.0  # the hymn's lowest note
    sample_rate_hz: Annotated[int, Field(ge=8000, le=48000)] = 16000
    hop_s: Annotated[float, Field(ge=0.001, le=1)] = 0.01  # between frames of the true pitch track
    slope_s: Positive = 0.08  # how long a smooth move takes, at most half its note
    vibrato_rate_hz: Positive = 5.5
    vibrato_width_cents: Positive = 100.0  # peak to peak
    timing_wobble: Annotated[float, Field(ge=0, le=0.5)] = 0.0  # each length varies by up to this share
    drift_cents_per_min: Annotated[float, Field(ge=-1200, le=1200)] = 0.0
    noise_snr_db: float | None = None  # none means no noise
    echo_rt60_s: Annotated[float, Field(gt=0, le=10)] | None = None  # none means no echo
    echo_wet_db: float = -6.0
    cymbal_every: Annotated[int, Field(ge=1)] | None = None  # in half-note units; none means no cymbals
    cymbal_db: float = 0.0

    @model_validator(mode="after")
    def sections_start_at_phrase_0_and_rise(self) -> Self:
        starts = [section.first_phrase for section in self.sections]
        if starts[0] != 0 or any(later <= earlier for earlier, later in zip(starts, starts[1:])):
            raise ValueError("sections must start at phrase 0 and then rise strictly")
        return self


class SynthInput(Contract):
    """The string to sing, how to sing it, and where to write the recording."""

    string: HymnString
    settings: SynthSettings
    out_path: NonEmpty


class GroundTruth(Contract):
    """What the audio nodes should find in a synthesised recording. These values are exact, so they follow
    conventions that a measurement would not.

    A note reached by a slide starts where the slide arrives. Its pitch starts moving up to `slope_s`
    earlier, so a note-onset detector that marks where the pitch starts to move will be early by up to
    that. Every confidence is 1.0, except a silent pitch frame's, which is 0.0. The true `step_cents` is
    always the setting, even in a section with no interval to measure, where a measured `StepSize` would
    be null. The pitch track covers the whole recording, echo tail included, with None wherever the voice
    is silent. Vibrato `width_cents` is peak to peak.
    """

    pitch_track: PitchTrack
    note_starts: NoteStarts
    syllable_times: SyllableTimes
    pulse_unit: PulseUnit
    step_size: StepSize


class SynthOutput(Contract):
    """The recording as the next nodes will hear it, and the answers they should find in it."""

    voice: Voice
    truth: GroundTruth
