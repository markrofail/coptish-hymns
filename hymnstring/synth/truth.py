"""Reads a score into the answers a recording of it should be measured against.

`pitch_at` is the one function that gives pitch (rule 13), so that the true pitch track and the sung
voice can't disagree. Rule numbers are those in docs/superpowers/plans/2026-11-02-synthesiser.md.
"""

import math
from fractions import Fraction

import numpy as np

from hymnstring.contracts import (
    GroundTruth,
    HymnString,
    NoteStarts,
    PitchTrack,
    PulseUnit,
    StepSize,
    SyllableTimes,
    SynthSettings,
)
from hymnstring.contracts.audio import NoteStart, PulseSection, StepSection, SyllableTime, Vibrato
from hymnstring.contracts.base import TimeSpan
from hymnstring.notation import parse_hymn
from hymnstring.synth.score import Score, build_score, sample_count


def pitch_at(score: Score, settings: SynthSettings, times: np.ndarray) -> np.ndarray:
    """Rules 13 to 16: the pitch in Hz at each time, NaN where no note is sounding."""
    t = np.asarray(times, dtype=float)
    hz = np.full(t.shape, np.nan)
    notes = score.notes
    if not notes:
        return hz

    starts = np.array([float(n.start) for n in notes])
    ends = np.array([float(n.end) for n in notes])
    cents = np.array([n.cents for n in notes])
    vibrato = np.array([n.kind == "vibrato" for n in notes])
    # rule 14: a slide takes the last `glide` seconds of its note, rising `rise` cents to the next note's
    glide = np.minimum(settings.slope_s, np.array([float(n.end - n.start) for n in notes]) / 2)
    rise = np.where([n.slides_on for n in notes], np.append(cents[1:], cents[-1]) - cents, 0.0)

    latest = np.searchsorted(starts, t, side="right") - 1  # the last note to have started, or -1
    # -1 wraps round to the last note in `ends`, and `latest >= 0` rules that out
    sounding = (latest >= 0) & (t < ends[latest])
    note, now = latest[sounding], t[sounding]

    along = np.clip((now - (ends[note] - glide[note])) / glide[note], 0.0, 1.0)  # share of the slide done
    wave = np.sin(2 * np.pi * settings.vibrato_rate_hz * (now - starts[note]))  # rule 15
    swing = np.where(vibrato[note], settings.vibrato_width_cents / 2 * wave, 0.0)
    total = cents[note] + rise[note] * along + swing + settings.drift_cents_per_min * now / 60  # rule 16
    hz[sounding] = settings.base_hz * np.exp2(total / 1200)
    return hz


def truth_of(score: Score, settings: SynthSettings) -> GroundTruth:
    """Rules 28 to 30: the five true values. Every confidence is 1.0, except a silent pitch frame's."""
    return GroundTruth(
        pitch_track=_pitch_track(score, settings),
        note_starts=_note_starts(score),
        syllable_times=_syllable_times(score),
        pulse_unit=_pulse_unit(score, settings),
        step_size=_step_size(score),
    )


def true_values(string: HymnString, settings: SynthSettings) -> GroundTruth:
    """The true values of a string sung with these settings. Makes no audio."""
    return truth_of(build_score(parse_hymn(string.text), settings), settings)


def _pitch_track(score: Score, settings: SynthSettings) -> PitchTrack:
    """Rule 29: a frame for each hop up to the last sample, counted exactly; the frame times are floats."""
    duration = Fraction(sample_count(score, settings), settings.sample_rate_hz)
    frames = math.ceil(duration / Fraction(settings.hop_s))
    f0 = pitch_at(score, settings, np.arange(frames) * settings.hop_s)
    silent = np.isnan(f0).tolist()
    return PitchTrack(
        hop_s=settings.hop_s,
        f0_hz=tuple(None if gap else hz for hz, gap in zip(f0.tolist(), silent)),
        confidence=tuple(0.0 if gap else 1.0 for gap in silent),
        vibrato=tuple(
            Vibrato(
                start_s=float(n.start),
                end_s=float(n.end),
                rate_hz=settings.vibrato_rate_hz,
                width_cents=settings.vibrato_width_cents,
            )
            for n in score.notes
            if n.kind == "vibrato"
        ),
    )


def _note_starts(score: Score) -> NoteStarts:
    """Rule 30: one start for each note, and a breath for each rest."""
    return NoteStarts(
        notes=tuple(
            NoteStart(start_s=float(n.start), syllable_index=n.syllable, cause=n.cause, confidence=1.0)
            for n in score.notes
        ),
        breaths=tuple(TimeSpan(start_s=float(r.start), end_s=float(r.end)) for r in score.rests),
    )


def _syllable_times(score: Score) -> SyllableTimes:
    """Rule 30: a syllable runs from its first note's start to its last note's end, pauses and all."""
    first: dict[int, Fraction] = {}
    last: dict[int, Fraction] = {}
    for n in score.notes:
        first.setdefault(n.syllable, n.start)
        last[n.syllable] = n.end
    return SyllableTimes(
        syllables=tuple(
            SyllableTime(start_s=float(first[i]), end_s=float(last[i]), syllable_index=i, confidence=1.0)
            for i in first  # in the order they first sound, which is their number
        ),
        catch_all=(),
    )


def _pulse_unit(score: Score, settings: SynthSettings) -> PulseUnit:
    """Rule 30: the tempo of each section, taken from the cymbals when they are on."""
    return PulseUnit(
        source="note_durations" if settings.cymbal_every is None else "cymbals",
        sections=tuple(
            PulseSection(
                start_s=float(s.start), end_s=float(s.end), half_note_s=s.half_note_s, confidence=1.0
            )
            for s in score.sections
        ),
    )


def _step_size(score: Score) -> StepSize:
    """Rule 30: the step of each section."""
    return StepSize(
        sections=tuple(
            StepSection(
                start_s=float(s.start), end_s=float(s.end), step_cents=s.step_cents, confidence=1.0
            )
            for s in score.sections
        )
    )
