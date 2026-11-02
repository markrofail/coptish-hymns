"""Lays a string out in exact time and pitch, with no sound involved.

Phrases follow each other with no gap, so the only silence is a pause in the string (rule 1). A later
chain is placed so that a motif keeps the pitch it first had, and when two motifs in a chain disagree
the first one wins (rule 5). Rule numbers are those in docs/superpowers/plans/2026-11-02-synthesiser.md.
"""

import math
from bisect import bisect_right
from collections.abc import Iterator
from dataclasses import dataclass
from fractions import Fraction
from itertools import groupby
from typing import Literal

import numpy as np

from hymnstring.contracts import SynthSettings
from hymnstring.notation import ChainedPhrase, FlatNote, FlatPause, Hymn, Move, Syllable, walk_chains

# which random source: the second number in each generator's seed (rule 22)
TIMING = 0
NOISE = 1
ECHO = 2
CYMBALS = 3

MAX_SECONDS = 1800  # so that a short string can't ask for an enormous recording

Cause = Literal["syllable_start", "pitch_change", "resung"]


class SynthError(ValueError):
    """The string can't be sung as asked: it is too long or too high, or no syllable starts it."""


@dataclass(frozen=True)
class SungNote:
    start: Fraction  # seconds, exact
    end: Fraction
    level: int  # in the hymn, not in its phrase
    cents: float  # above the hymn's lowest note
    kind: Literal["note", "vibrato", "fast"]
    syllable: int
    cause: Cause
    slides_on: bool  # glides into the next note, which a smooth move leads to


@dataclass(frozen=True)
class Rest:
    start: Fraction
    end: Fraction


@dataclass(frozen=True)
class TimedSection:
    start: Fraction
    end: Fraction
    half_note_s: float  # the setting, even when the timing wobbles
    step_cents: float


@dataclass(frozen=True)
class Score:
    notes: tuple[SungNote, ...]
    rests: tuple[Rest, ...]
    sections: tuple[TimedSection, ...]
    end: Fraction  # a trailing pause counts


def build_score(hymn: Hymn, settings: SynthSettings) -> Score:
    """The hymn in exact time and pitch. Raises SynthError if it lasts too long, climbs too high, has
    no syllable on its first note, or has a section that starts after its last phrase."""
    in_section = _sections_of_phrases(hymn, settings)
    walked = list(walk_chains(hymn))
    offsets = _chain_offsets(walked)
    note_events = [(w, e) for w in walked for e in w.flat.events if isinstance(e, FlatNote)]
    levels = [e.level + offsets[w.chain] for w, e in note_events]
    cents = _cents(levels, [in_section[w.index] for w, _ in note_events], settings)
    upcoming = iter(zip(levels, cents, _slides(walked)))  # what each note brings with it, in order
    wobbles = _wobbles(settings)

    notes: list[SungNote] = []
    rests: list[Rest] = []
    phrase_starts: list[Fraction] = []
    now = Fraction(0)
    syllable, previous = -1, None
    for w in walked:
        phrase_starts.append(now)
        half_note = Fraction(settings.sections[in_section[w.index]].half_note_s)
        for event in w.flat.events:
            end = now + half_note * event.length * next(wobbles)
            if end > MAX_SECONDS:
                raise SynthError(f"a hymn can last at most {MAX_SECONDS} seconds")
            if isinstance(event, FlatPause):
                if rests and rests[-1].end == now:  # adjacent pauses are one rest
                    rests[-1] = Rest(rests[-1].start, end)
                else:
                    rests.append(Rest(now, end))
            else:
                level, pitch, slides_on = next(upcoming)
                if isinstance(event.lyric, Syllable):
                    syllable += 1
                    cause: Cause = "syllable_start"
                elif syllable < 0:
                    raise SynthError("the first note must start a syllable, as in a:2")
                else:
                    cause = "pitch_change" if level != previous else "resung"
                notes.append(SungNote(now, end, level, pitch, event.kind, syllable, cause, slides_on))
                previous = level
            now = end

    _check_the_top(cents, now, settings)
    bounds = [phrase_starts[s.first_phrase] for s in settings.sections] + [now]
    sections = tuple(
        TimedSection(start, end, s.half_note_s, s.step_cents)
        for s, start, end in zip(settings.sections, bounds, bounds[1:])
    )
    return Score(tuple(notes), tuple(rests), sections, now)


def sample_count(score: Score, settings: SynthSettings) -> int:
    """Rule 17: the score's samples, then the echo's tail when echo is on, both counted exactly."""
    count = math.ceil(score.end * settings.sample_rate_hz)
    if settings.echo_rt60_s is not None:
        count += math.ceil(Fraction(settings.echo_rt60_s) * settings.sample_rate_hz)
    return count


def _sections_of_phrases(hymn: Hymn, settings: SynthSettings) -> list[int]:
    """The section each phrase belongs to. A section has to start on a phrase the hymn has."""
    starts = [section.first_phrase for section in settings.sections]
    for number, first in enumerate(starts):
        if first >= len(hymn.phrases):
            raise SynthError(
                f"section {number} starts at phrase {first}, but phrases count from 0 "
                f"and the hymn has only {len(hymn.phrases)}"
            )
    return [bisect_right(starts, index) - 1 for index in range(len(hymn.phrases))]


def _chain_offsets(walked: list[ChainedPhrase]) -> dict[int, int]:
    """Rule 5: how many hymn levels above its own level 0 each chain sits."""
    known: dict[int, int] = {}  # motif label -> hymn level of its plain occurrences
    offsets: dict[int, int] = {}
    for chain, phrases in groupby(walked, key=lambda w: w.chain):
        uses = [use for w in phrases for use in w.flat.motifs]
        offset = next((known[u.label] + u.shift - u.start_level for u in uses if u.label in known), 0)
        for use in uses:
            known.setdefault(use.label, offset + use.start_level - use.shift)
        offsets[chain] = offset
    return offsets


def _cents(levels: list[int], sections: list[int], settings: SynthSettings) -> list[float]:
    """Rules 6 and 7: cents grow one section at a time, from where the section before ended."""
    raw: list[float] = []
    origin_level, origin_cents = 0, 0.0
    for i, level in enumerate(levels):
        if i and sections[i] != sections[i - 1]:
            origin_level, origin_cents = levels[i - 1], raw[i - 1]
        raw.append(origin_cents + (level - origin_level) * settings.sections[sections[i]].step_cents)
    lowest = min(raw, default=0.0)
    return [value - lowest for value in raw]


def _slides(walked: list[ChainedPhrase]) -> list[bool]:
    """Rule 11, for each note: is the very next event a note that a smooth, non-zero move leads to?"""
    is_note: list[bool] = []
    smooth_into: list[bool] = []
    for w in walked:
        for position, event in enumerate(w.flat.events):
            smooth = False
            if isinstance(event, FlatNote):
                move = w.phrase.join if position == 0 else event.move  # a join comes before the first note
                smooth = isinstance(move, Move) and not move.abrupt and move.change != 0
            is_note.append(isinstance(event, FlatNote))
            smooth_into.append(smooth)
    next_is_smooth = smooth_into[1:] + [False]
    return [smooth for smooth, note in zip(next_is_smooth, is_note) if note]


def _wobbles(settings: SynthSettings) -> Iterator[Fraction]:
    """Rule 3: the factor on each event's length, in event order. Exactly 1 unless the timing wobbles."""
    rng = np.random.default_rng([settings.seed, TIMING])
    width = settings.timing_wobble
    while True:
        yield Fraction(float(1 + rng.uniform(-width, width))) if width else Fraction(1)


def _check_the_top(cents: list[float], end: Fraction, settings: SynthSettings) -> None:
    """Rule 8: the top note, its vibrato and any rising drift stay under half the sample rate.
    Checked in logs, so that a huge level can't overflow."""
    rising = max(0.0, settings.drift_cents_per_min) * float(end) / 60
    top_cents = max(cents, default=0.0) + settings.vibrato_width_cents / 2 + rising
    if math.log2(settings.base_hz) + top_cents / 1200 >= math.log2(settings.sample_rate_hz / 2):
        raise SynthError(
            f"the highest pitch must stay under half the sample rate ({settings.sample_rate_hz // 2} Hz): "
            "lower base_hz, the climb or the vibrato, or raise sample_rate_hz"
        )
