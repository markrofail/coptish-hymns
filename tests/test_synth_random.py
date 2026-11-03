import ast
import inspect
import math
import re
from fractions import Fraction
from typing import NamedTuple

import pytest

import hymnstring.synth.random_hymns as generator
from hymnstring.synth import random_hymn, random_settings, true_values

# Every token in SPEC.md's table, as a pattern that finds it in a hymn's text (one line per phrase).
# The sizes n and k are any whole number, and N is a repeat count.
TOKENS = {
    "plain note": r"(?:^|[ \[(])\d+(?=[ \])]|$)",
    "vibrato note ~n": r"~\d",
    "pause .n": r"(?:^| )\.\d",
    "fast group": r">\d+\{",
    "fast group with a move inside": r">\d+\{[^}]*[\^v!][^}]*\}",
    "fast group across syllables": r">\d+\{[^}]*[^\W\d_]+:\*[^}]*[^\W\d_]+:\*",
    "step up ^": r"(?:^| )\^(?= )",
    "step down v": r"(?:^| )v(?= )",
    "step up ^n": r"(?:^| )\^\d",
    "step down vn": r"(?:^| )v\d",
    "bare corner !": r"(?:^| )!(?= )",
    "corner !^ or !v": r"!(?:\^|v)(?= )",
    "corner !^n or !vn": r"!(?:\^|v)\d",
    "repeat xN": r"\)x\d+(?![\d^v])",
    "repeat xN^": r"\)x\d+\^(?!\d)",
    "repeat xNv": r"\)x\d+v(?!\d)",
    "repeat xN^K or xNvK": r"\)x\d+[\^v]\d",
    "motif #n[": r"#\d+\[",
    "shifted motif #n+k[ or #n-k[": r"#\d+[+-]\d+\[",
    "syllable": r"[^\W\d_]+:[~\d*]",
    "vowel label": r"\([^\W\d_]+\):[~\d*]",
    "added letter <+": r"<\+",
    "silent letter <-": r"<-",
    "smooth join": r"^p\d+ \w+: [\^v]\d* ",
    "corner join": r"^p\d+ \w+: !(?:[\^v]\d*)? ",
    "equals join": r"^p\d+ \w+: = ",
    "no join after the first phrase": r"^p[2-9]\d* \w+: (?!(?:!?[\^v]\d*|!|=) )",
}
JOIN = re.compile(r"(?:!?[\^v]\d*|!|=) ")


@pytest.fixture(scope="module")
def texts():
    return [random_hymn(seed).string.text for seed in range(50)]


@pytest.mark.parametrize("name", TOKENS)
def test_every_token_appears_in_some_hymn(texts, name):
    assert any(re.search(TOKENS[name], text, re.MULTILINE) for text in texts)


def test_a_motif_is_shared_across_chains(texts):
    def shares(text):
        chains = []  # the motif labels each chain uses
        for line in text.split("\n"):
            notation = line.split(": ", 1)[1]
            if not chains or not JOIN.match(notation):  # a phrase with no join starts a new chain
                chains.append(set())
            chains[-1] |= set(re.findall(r"#(\d+)", notation))
        return any(a & b for i, a in enumerate(chains) for b in chains[i + 1 :])

    assert any(shares(text) for text in texts)


def test_the_same_seed_gives_the_same_hymn():
    assert random_hymn(7) == random_hymn(7)


def test_another_seed_gives_another_hymn():
    assert random_hymn(7).string != random_hymn(8).string


# -- the milestone's check: the true values match the string

# The plan that `random_hymn` writes beside each string, and `worked_out` below, are the check's two
# independent derivations. Neither may use the code that builds the true values.


class Sung(NamedTuple):
    start: Fraction
    end: Fraction
    section: int
    event: object  # the PlannedEvent
    slides_on: bool
    cents: float = 0.0


class Worked(NamedTuple):
    """What the true values should be, in their own units."""

    notes: list  # (start_s, syllable_index, cause)
    breaths: list  # (start_s, end_s)
    syllables: list  # (start_s, end_s), by syllable number
    pulse: list  # (start_s, end_s, half_note_s)
    steps: list  # (start_s, end_s, step_cents)
    vibrato: list  # (start_s, end_s, rate_hz, width_cents)
    frames: list  # Hz at each frame of the pitch track, None in silence


def section_of(settings, phrase):
    """The section a phrase sings in: the last one that has started by then."""
    return max(i for i, section in enumerate(settings.sections) if section.first_phrase <= phrase)


def worked_out(hymn, settings):
    """The answers for a planned hymn, from its events and the settings alone: exact times (rules 1
    and 2), rests (12), cents (6 and 7), the frame count (17 and 29) and each frame's pitch (13 to 15)."""
    events, sections = hymn.events, settings.sections
    now = Fraction(0)
    notes, rests, section_starts = [], [], {}
    for position, event in enumerate(events):
        k = section_of(settings, event.phrase)
        section_starts.setdefault(k, now)
        end = now + Fraction(sections[k].half_note_s) * event.length
        if event.kind == "pause":
            if rests and rests[-1][1] == now:  # adjacent pauses are one rest
                rests[-1][1] = end
            else:
                rests.append([now, end])
        else:
            # a note slides when the very next event is a note that a smooth, non-zero move reaches
            slides_on = position + 1 < len(events) and events[position + 1].slides_in
            notes.append(Sung(now, end, k, event, slides_on))
        now = end

    raw, origin_level, origin_cents = [], 0, 0.0  # each section carries on from where the one before ended
    for i, note in enumerate(notes):
        if i and note.section != notes[i - 1].section:
            origin_level, origin_cents = notes[i - 1].event.level, raw[i - 1]
        raw.append(origin_cents + (note.event.level - origin_level) * sections[note.section].step_cents)
    notes = [note._replace(cents=value - min(raw)) for note, value in zip(notes, raw)]

    first, last = {}, {}
    for note in notes:
        first.setdefault(note.event.syllable, note.start)
        last[note.event.syllable] = note.end
    edges = [section_starts[k] for k in range(len(sections))] + [now]

    samples = math.ceil(now * settings.sample_rate_hz)
    count = math.ceil(Fraction(samples, settings.sample_rate_hz) / Fraction(settings.hop_s))
    frames, k = [], 0
    for i in range(count):
        t = i * settings.hop_s
        while k < len(notes) and t >= float(notes[k].end):
            k += 1
        if k == len(notes) or t < float(notes[k].start):
            frames.append(None)
            continue
        note = notes[k]
        cents = note.cents
        if note.slides_on:  # the last `glide` seconds, rising to the next note
            glide = min(settings.slope_s, float(note.end - note.start) / 2)
            along = (t - (float(note.end) - glide)) / glide
            cents += (notes[k + 1].cents - note.cents) * min(1.0, max(0.0, along))
        if note.event.kind == "vibrato":
            cents += settings.vibrato_width_cents / 2 * math.sin(
                2 * math.pi * settings.vibrato_rate_hz * (t - float(note.start))
            )
        frames.append(settings.base_hz * 2 ** (cents / 1200))

    return Worked(
        notes=[(float(n.start), n.event.syllable, n.event.cause) for n in notes],
        breaths=[(float(start), float(end)) for start, end in rests],
        syllables=[(float(first[s]), float(last[s])) for s in sorted(first)],
        pulse=[(float(a), float(b), s.half_note_s) for s, a, b in zip(sections, edges, edges[1:])],
        steps=[(float(a), float(b), s.step_cents) for s, a, b in zip(sections, edges, edges[1:])],
        vibrato=[
            (float(n.start), float(n.end), settings.vibrato_rate_hz, settings.vibrato_width_cents)
            for n in notes
            if n.event.kind == "vibrato"
        ],
        frames=frames,
    )


@pytest.mark.parametrize("seed", range(50))
def test_true_values_match_the_string(seed):
    hymn = random_hymn(seed)
    settings = random_settings(seed, len(hymn.string.phrases))
    truth = true_values(hymn.string, settings)
    want = worked_out(hymn, settings)

    starts, track = truth.note_starts, truth.pitch_track
    assert [(n.start_s, n.syllable_index, n.cause) for n in starts.notes] == want.notes
    assert [(b.start_s, b.end_s) for b in starts.breaths] == want.breaths
    assert [(s.start_s, s.end_s) for s in truth.syllable_times.syllables] == want.syllables
    assert truth.syllable_times.catch_all == ()
    assert [(s.start_s, s.end_s, s.half_note_s) for s in truth.pulse_unit.sections] == want.pulse
    assert [(s.start_s, s.end_s, s.step_cents) for s in truth.step_size.sections] == want.steps
    assert [(v.start_s, v.end_s, v.rate_hz, v.width_cents) for v in track.vibrato] == want.vibrato
    assert truth.pitch_track.hop_s == settings.hop_s

    certain = [*starts.notes, *truth.syllable_times.syllables]
    certain += [*truth.pulse_unit.sections, *truth.step_size.sections]
    assert {item.confidence for item in certain} == {1.0}  # rule 28
    assert len(track.f0_hz) == len(track.confidence) == len(want.frames)
    assert [f is None for f in track.f0_hz] == [f is None for f in want.frames]
    assert [f for f in track.f0_hz if f is not None] == pytest.approx(
        [f for f in want.frames if f is not None], rel=1e-12
    )
    assert list(track.confidence) == [0.0 if f is None else 1.0 for f in want.frames]


def true_spans(truth):
    """(is a note, seconds) for each note and each rest in time order, from the true values alone."""
    notes, breaths = truth.note_starts.notes, truth.note_starts.breaths
    marks = sorted([(n.start_s, True) for n in notes] + [(b.start_s, False) for b in breaths])
    stops = [start for start, _ in marks[1:]] + [truth.pulse_unit.sections[-1].end_s]
    return [(is_note, stop - start) for (start, is_note), stop in zip(marks, stops)]


def planned_spans(hymn, settings):
    """The same, from the plan: each note, and each run of pauses as one rest."""
    spans = []
    for event in hymn.events:
        seconds = settings.sections[section_of(settings, event.phrase)].half_note_s * float(event.length)
        if event.kind == "pause" and spans and not spans[-1][0]:
            spans[-1] = (False, spans[-1][1] + seconds)
        else:
            spans.append((event.kind != "pause", seconds))
    return spans


@pytest.mark.parametrize("seed", range(10))
def test_wobble_keeps_the_true_values_consistent(seed):
    hymn = random_hymn(seed)
    settings = random_settings(seed, len(hymn.string.phrases)).model_copy(update={"timing_wobble": 0.15})
    truth = true_values(hymn.string, settings)

    true, planned = true_spans(truth), planned_spans(hymn, settings)
    assert [is_note for is_note, _ in true] == [is_note for is_note, _ in planned]  # same notes and rests
    assert all(abs(got - want) <= 0.15 * want + 1e-9 for (_, got), (_, want) in zip(true, planned))
    assert any(abs(got - want) > 1e-6 for (_, got), (_, want) in zip(true, planned))  # it did something
    assert [(n.syllable_index, n.cause) for n in truth.note_starts.notes] == [
        (e.syllable, e.cause) for e in hymn.events if e.kind != "pause"
    ]


# -- the generator keeps to what the later tasks rely on


def test_hymns_and_settings_keep_to_their_ranges():
    hops, slopes, section_counts = set(), set(), set()
    for seed in range(50):
        hymn = random_hymn(seed)
        phrases = len(hymn.string.phrases)
        settings = random_settings(seed, phrases)
        assert 1 <= phrases <= 4 and {event.phrase for event in hymn.events} == set(range(phrases))
        assert {event.level for event in hymn.events if event.kind != "pause"} <= set(range(-5, 6))
        assert 1 <= len(settings.sections) <= min(3, phrases)
        assert all(0.15 <= s.half_note_s <= 0.5 and 80 <= s.step_cents <= 240 for s in settings.sections)
        assert 100 <= settings.base_hz <= 180 and 4.5 <= settings.vibrato_rate_hz <= 6.5
        assert 60 <= settings.vibrato_width_cents <= 140
        hops.add(settings.hop_s)
        slopes.add(settings.slope_s)
        section_counts.add(len(settings.sections))
    assert hops == {0.005, 0.01, 0.02} and slopes == {0.04, 0.08, 0.12} and section_counts == {1, 2, 3}


# -- the independence the check rests on

LEANS_ON = {
    "flatten", "walk_chains", "score", "truth", "build_score", "pitch_at", "true_values", "truth_of",
}


def names_in(source):
    """Every name that some code imports, reads or calls."""
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Import):
            names |= {part for alias in node.names for part in alias.name.split(".")}
        elif isinstance(node, ast.ImportFrom):
            names |= set(node.module.split(".")) | {alias.name for alias in node.names}
    return names


def test_the_plan_and_the_worked_out_answers_do_not_use_the_code_they_check():
    assert names_in(inspect.getsource(generator)) & LEANS_ON == set()
    assert names_in(inspect.getsource(worked_out) + inspect.getsource(section_of)) & LEANS_ON == set()
