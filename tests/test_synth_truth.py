import numpy as np
import pytest

from hymnstring.contracts import HymnString, SynthSettings
from hymnstring.contracts.synth import SynthSection
from hymnstring.notation import parse_hymn
from hymnstring.synth import build_score, pitch_at, true_values

DEMO = "p1 ltr: #1[A:2 ^ 1 v 1] ^ lē:~2 .2 v (lou:1)x3^ >1{i:*} a:2 !v2 #1[(a):2 ^ 1 v 1] v 4"


def settings(half_note_s=0.5, step_cents=200.0, base_hz=100.0, **more):
    return SynthSettings(
        seed=1,
        sections=(SynthSection(first_phrase=0, half_note_s=half_note_s, step_cents=step_cents),),
        base_hz=base_hz,
        **more,
    )


def two_sections():
    return SynthSettings(
        seed=1,
        sections=(
            SynthSection(first_phrase=0, half_note_s=0.5, step_cents=200.0),
            SynthSection(first_phrase=1, half_note_s=0.25, step_cents=100.0),
        ),
        base_hz=100.0,
    )


def string_of(text):
    """The HymnString for `p1 ltr: ...` lines."""
    phrases = []
    for line in text.split("\n"):
        head, notation = line.split(": ", 1)
        phrase_id, direction = head.split()
        phrases.append({"phrase_id": phrase_id, "direction": direction, "notation": notation})
    return HymnString.model_validate({"format_version": 1, "phrases": phrases})


def demo_string():
    return string_of(DEMO)


def at(score, cfg, *times):
    return pitch_at(score, cfg, np.array(times))


# -- the pitch curve (rules 13 to 16)


def test_notes_and_a_slide():
    # 0.5 s per half note, one octave per level, a slide over the last 0.1 s of the first note
    cfg = settings(half_note_s=0.5, step_cents=1200.0, base_hz=100.0, slope_s=0.1)
    score = build_score(parse_hymn("p1 ltr: a:2 ^ 2"), cfg)

    values = at(score, cfg, 0.5, 0.9, 0.95, 1.0, 1.99)
    assert values == pytest.approx([100, 100, 100 * 2**0.5, 200, 200])
    assert np.isnan(at(score, cfg, 2.0)[0])  # the end is not sounding


def test_a_slide_is_at_most_half_its_note():
    cfg = settings(half_note_s=0.2, step_cents=1200.0, base_hz=100.0, slope_s=0.08)
    score = build_score(parse_hymn("p1 ltr: >1{a:* ^ *}"), cfg)  # two notes of 0.1 s

    assert at(score, cfg, 0.05, 0.075) == pytest.approx([100, 100 * 2**0.5])


def test_an_abrupt_move_steps_at_the_note():
    cfg = settings(half_note_s=0.5, step_cents=1200.0, base_hz=100.0)
    score = build_score(parse_hymn("p1 ltr: a:2 !^ 2"), cfg)

    assert at(score, cfg, 0.99, 1.0) == pytest.approx([100, 200])


def test_vibrato_is_peak_to_peak():
    cfg = settings(half_note_s=0.5, base_hz=100.0, vibrato_rate_hz=5.0, vibrato_width_cents=100.0)
    score = build_score(parse_hymn("p1 ltr: a:~4"), cfg)

    assert at(score, cfg, 0.05, 0.15) == pytest.approx([100 * 2 ** (50 / 1200), 100 * 2 ** (-50 / 1200)])


def test_vibrato_carries_on_through_a_slide():
    cfg = settings(
        half_note_s=0.5, step_cents=1200.0, base_hz=100.0, slope_s=0.1, vibrato_rate_hz=5.0,
        vibrato_width_cents=100.0,
    )
    score = build_score(parse_hymn("p1 ltr: a:~2 ^ 2"), cfg)

    # 0.85: the slide hasn't begun, the sine is at its crest. 0.95: half way up the octave, and at its trough.
    # 1.05: the next note is plain.
    assert at(score, cfg, 0.85, 0.95, 1.05) == pytest.approx(
        [100 * 2 ** (50 / 1200), 100 * 2 ** (550 / 1200), 200]
    )


def test_vibrato_starts_afresh_with_its_note():
    # the second note starts at 0.5 s, half a cycle into 5 Hz, and its own cycle begins there
    cfg = settings(half_note_s=0.5, base_hz=100.0, vibrato_rate_hz=5.0, vibrato_width_cents=100.0)
    score = build_score(parse_hymn("p1 ltr: a:1 b:~2"), cfg)

    assert at(score, cfg, 0.55) == pytest.approx([100 * 2 ** (50 / 1200)])


def test_drift_adds_cents_over_time():
    cfg = settings(half_note_s=20.0, base_hz=100.0, drift_cents_per_min=120.0)
    score = build_score(parse_hymn("p1 ltr: a:4"), cfg)

    assert at(score, cfg, 30.0) == pytest.approx([100 * 2 ** (60 / 1200)])


def test_nothing_sounds_before_the_first_note():
    cfg = settings()
    score = build_score(parse_hymn("p1 ltr: .2 a:2"), cfg)  # a pause first: parse_hymn allows it, a HymnString doesn't

    assert np.isnan(at(score, cfg, -1.0, 0.0, 0.99)).all()
    assert at(score, cfg, 1.0) == pytest.approx([100])


def test_a_score_with_no_notes_is_silent():
    cfg = settings()
    score = build_score(parse_hymn("p1 ltr: .2"), cfg)  # one pause: parse_hymn allows it, a HymnString doesn't

    assert np.isnan(at(score, cfg, 0.0, 0.5, 5.0)).all()


# -- the demo phrase from CONTEXT.md section 3, at 0.5 s per half note and 200 cents (rules 28 to 30)


def test_demo_truth():
    truth = true_values(demo_string(), settings())

    assert [n.start_s for n in truth.note_starts.notes] == [0, 1, 1.5, 2, 4, 4.5, 5, 5.5, 6, 7, 8, 8.5, 9]
    assert [(b.start_s, b.end_s) for b in truth.note_starts.breaths] == [(3, 4)]
    assert [(s.start_s, s.end_s) for s in truth.syllable_times.syllables] == [
        (0, 2), (2, 3), (4, 5.5), (5.5, 6), (6, 11),
    ]
    assert truth.syllable_times.catch_all == ()
    assert [(s.start_s, s.end_s, s.half_note_s, s.confidence) for s in truth.pulse_unit.sections] == [(0, 11, 0.5, 1)]
    assert truth.pulse_unit.source == "note_durations"
    assert [(s.start_s, s.end_s, s.step_cents, s.confidence) for s in truth.step_size.sections] == [(0, 11, 200, 1)]


def test_demo_notes_carry_their_syllable_and_cause():
    truth = true_values(demo_string(), settings())

    assert [n.syllable_index for n in truth.note_starts.notes] == [0, 0, 0, 1, 2, 2, 2, 3, 4, 4, 4, 4, 4]
    assert [n.cause for n in truth.note_starts.notes] == [
        "syllable_start", "pitch_change", "pitch_change", "syllable_start", "syllable_start",
        "pitch_change", "pitch_change", "syllable_start", "syllable_start", "pitch_change",
        "pitch_change", "pitch_change", "pitch_change",
    ]
    assert [s.syllable_index for s in truth.syllable_times.syllables] == [0, 1, 2, 3, 4]


def test_every_true_note_and_syllable_is_certain():
    truth = true_values(demo_string(), settings())

    assert {n.confidence for n in truth.note_starts.notes} == {1.0}
    assert {s.confidence for s in truth.syllable_times.syllables} == {1.0}


def test_demo_pitch_track():
    track = true_values(demo_string(), settings()).pitch_track

    assert track.hop_s == 0.01
    assert len(track.f0_hz) == 1100
    silent = [i for i, f0 in enumerate(track.f0_hz) if f0 is None]
    assert silent == list(range(300, 400))
    assert all(track.confidence[i] == (0.0 if i in silent else 1.0) for i in range(1100))
    assert [(v.start_s, v.end_s, v.rate_hz, v.width_cents) for v in track.vibrato] == [(2, 3, 5.5, 100)]


def test_the_echo_tail_is_framed_and_silent():
    truth = true_values(demo_string(), settings(echo_rt60_s=0.5))

    f0 = truth.pitch_track.f0_hz
    assert len(f0) == 1150  # 11.5 s of samples
    assert f0[1099] is not None and all(value is None for value in f0[1100:])
    assert [n.start_s for n in truth.note_starts.notes] == [0, 1, 1.5, 2, 4, 4.5, 5, 5.5, 6, 7, 8, 8.5, 9]


def test_cymbals_change_the_pulse_source():
    truth = true_values(demo_string(), settings(cymbal_every=2))

    assert truth.pulse_unit.source == "cymbals"
    assert [(s.start_s, s.end_s, s.half_note_s) for s in truth.pulse_unit.sections] == [(0, 11, 0.5)]


def test_a_pause_inside_a_syllable_is_inside_its_span():
    truth = true_values(string_of("p1 ltr: a:2 .2 2"), settings())

    assert [(s.start_s, s.end_s) for s in truth.syllable_times.syllables] == [(0, 3)]
    assert [(b.start_s, b.end_s) for b in truth.note_starts.breaths] == [(1, 2)]


def test_two_sections_give_two_true_sections():
    truth = true_values(string_of("p1 ltr: a:2 ^ 2\np2 ltr: ^ b:2 ^ 2"), two_sections())

    assert [(s.start_s, s.end_s, s.half_note_s) for s in truth.pulse_unit.sections] == [(0, 2, 0.5), (2, 3, 0.25)]
    assert [(s.start_s, s.end_s, s.step_cents) for s in truth.step_size.sections] == [(0, 2, 200), (2, 3, 100)]


def test_the_frame_count_is_exact_not_floating_point():
    # 69.9 ms is 560 samples at 8 kHz, which is exactly 70 ms: seven frames of 10 ms. In floating point
    # 0.07 / 0.01 is 7.000000000000001, which would count an eighth.
    cfg = settings(half_note_s=0.0699, sample_rate_hz=8000)

    assert len(true_values(string_of("p1 ltr: a:1"), cfg).pitch_track.f0_hz) == 7
