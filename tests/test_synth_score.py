from fractions import Fraction

import numpy as np
import pytest

from hymnstring.contracts import SynthSettings
from hymnstring.contracts.synth import SynthSection
from hymnstring.notation import parse_hymn
from hymnstring.synth import (
    CYMBALS,
    ECHO,
    MAX_SECONDS,
    NOISE,
    TIMING,
    SynthError,
    TimedSection,
    build_score,
    sample_count,
)

DEMO = "p1 ltr: #1[A:2 ^ 1 v 1] ^ lē:~2 .2 v (lou:1)x3^ >1{i:*} a:2 !v2 #1[(a):2 ^ 1 v 1] v 4"


def settings(half_note_s=0.5, step_cents=200.0, **more):
    return SynthSettings(
        seed=1,
        sections=(SynthSection(first_phrase=0, half_note_s=half_note_s, step_cents=step_cents),),
        **more,
    )


def score_of(text, **more):
    return build_score(parse_hymn(text), settings(**more))


def two_sections():
    return SynthSettings(
        seed=1,
        sections=(
            SynthSection(first_phrase=0, half_note_s=0.5, step_cents=200.0),
            SynthSection(first_phrase=1, half_note_s=0.25, step_cents=100.0),
        ),
    )


def spans(items):
    return [(float(item.start), float(item.end)) for item in items]


# -- the demo phrase from CONTEXT.md section 3, at 0.5 s per half note and 200 cents


def test_demo_times():
    score = score_of(DEMO)
    assert [float(n.start) for n in score.notes] == [0, 1, 1.5, 2, 4, 4.5, 5, 5.5, 6, 7, 8, 8.5, 9]
    assert [float(n.end) for n in score.notes] == [1, 1.5, 2, 3, 4.5, 5, 5.5, 6, 7, 8, 8.5, 9, 11]
    assert [(float(r.start), float(r.end)) for r in score.rests] == [(3, 4)]
    assert score.end == 11


def test_demo_pitch_follows_the_table_in_context():
    assert [n.cents for n in score_of(DEMO).notes] == [
        200, 400, 200, 400, 200, 400, 600, 600, 600, 200, 400, 200, 0,
    ]


def test_demo_syllables_and_causes():
    notes = score_of(DEMO).notes
    assert [n.syllable for n in notes] == [0, 0, 0, 1, 2, 2, 2, 3, 4, 4, 4, 4, 4]
    assert [n.cause for n in notes] == [
        "syllable_start", "pitch_change", "pitch_change", "syllable_start", "syllable_start",
        "pitch_change", "pitch_change", "syllable_start", "syllable_start", "pitch_change",
        "pitch_change", "pitch_change", "pitch_change",
    ]
    assert [n.kind for n in notes].count("vibrato") == 1 and notes[3].kind == "vibrato"
    assert notes[7].kind == "fast"


def test_demo_slides():
    assert [n.slides_on for n in score_of(DEMO).notes] == [
        True, True, True, False, True, True, False, False, False, True, True, True, False,
    ]


def test_demo_levels_are_the_hymns_own():
    assert [n.level for n in score_of(DEMO).notes] == [0, 1, 0, 1, 0, 1, 2, 2, 2, 0, 1, 0, -1]


def test_one_section_covers_the_whole_hymn():
    assert score_of(DEMO).sections == (TimedSection(Fraction(0), Fraction(11), 0.5, 200.0),)


# -- time (rules 1 to 4)


def test_phrases_follow_each_other_with_no_gap():
    score = score_of("p1 ltr: a:2\np2 ltr: b:2")

    assert spans(score.notes) == [(0, 1), (1, 2)]
    assert score.rests == ()
    assert score.end == 2


def test_fast_notes_split_their_length_exactly():
    score = score_of("p1 ltr: >2{ⲧⲓ:* ^ ⲛⲉ:* v ⲣⲁ:*}", half_note_s=0.6)
    assert score.notes[1].start == Fraction(0.6) * Fraction(2, 3)
    assert score.end == Fraction(0.6) * 2


def test_wobble_stays_within_its_bound_and_keeps_notes_touching():
    score = score_of("p1 ltr: a:2 2 2 2 2 2 2 2", timing_wobble=0.15)
    lengths = [float(n.end - n.start) for n in score.notes]
    assert all(0.85 <= length <= 1.15 for length in lengths)
    assert len(set(lengths)) == 8
    assert all(a.end == b.start for a, b in zip(score.notes, score.notes[1:]))


def test_the_same_seed_gives_the_same_wobble():
    text = "p1 ltr: a:2 2 2 2"

    assert score_of(text, timing_wobble=0.15) == score_of(text, timing_wobble=0.15)


def test_another_seed_gives_another_wobble():
    hymn = parse_hymn("p1 ltr: a:2 2 2 2")
    cfg = settings(timing_wobble=0.15)

    first = build_score(hymn, cfg)
    second = build_score(hymn, cfg.model_copy(update={"seed": 2}))

    assert [n.end for n in first.notes] != [n.end for n in second.notes]


def test_each_event_takes_one_draw_and_a_pause_takes_its_turn():
    rng = np.random.default_rng([1, TIMING])
    wobble = [Fraction(float(1 + rng.uniform(-0.15, 0.15))) for _ in range(3)]
    unit = Fraction(1, 2) * 2  # a length of 2 at 0.5 s per half note

    score = score_of("p1 ltr: a:2 .2 2", timing_wobble=0.15)

    assert score.notes[0].end == unit * wobble[0]
    assert (score.rests[0].start, score.rests[0].end) == (unit * wobble[0], unit * (wobble[0] + wobble[1]))
    assert score.notes[1].end == unit * sum(wobble)


def test_without_wobble_the_seed_changes_nothing():
    hymn = parse_hymn(DEMO)

    assert build_score(hymn, settings().model_copy(update={"seed": 99})) == build_score(hymn, settings())


def test_wobble_moves_the_true_times_but_not_the_tempo():
    score = score_of("p1 ltr: a:2 2", timing_wobble=0.15)

    assert score.sections == (TimedSection(Fraction(0), score.end, 0.5, 200.0),)
    assert score.end != 2


def test_an_absurd_length_fails_at_once():
    with pytest.raises(SynthError, match="1800"):
        score_of("p1 ltr: a:999999999")


def test_a_hymn_exactly_at_the_limit_is_allowed():
    assert score_of("p1 ltr: a:1800", half_note_s=1.0).end == 1800


def test_a_hymn_a_half_note_over_the_limit_is_refused():
    with pytest.raises(SynthError, match="1800"):
        score_of("p1 ltr: a:1801", half_note_s=1.0)


def test_many_short_notes_reach_the_limit_too():
    with pytest.raises(SynthError, match="1800"):
        score_of("p1 ltr: a:1 " + "1 " * 4000)  # 4001 notes of 0.5 s


# -- chains (rule 5): a later chain is placed so that a motif keeps its pitch


def test_a_new_chain_starts_where_its_motif_already_sits():
    score = score_of("p1 ltr: a:1 ^ #1[1 ^ 1]\np2 ltr: b:1 ^2 #1[1 ^ 1]")

    assert [n.cents for n in score.notes] == [200, 400, 600, 0, 400, 600]


def test_a_new_chain_with_no_shared_motif_starts_at_hymn_level_0():
    score = score_of("p1 ltr: a:1 ^ 1\np2 ltr: b:1 v 1")

    assert [n.cents for n in score.notes] == [200, 400, 200, 0]


def test_a_shifted_motif_anchors_a_chain_at_its_shift():
    score = score_of("p1 ltr: a:1 #1[1]\np2 ltr: b:1 #1+2[1]")

    assert [n.cents for n in score.notes] == [0, 0, 400, 400]


def test_the_first_motif_wins_when_two_disagree():
    score = score_of("p1 ltr: a:1 #1[1] ^ #2[1]\np2 ltr: b:1 #1[1] ^2 #2[1]")

    assert [n.cents for n in score.notes] == [0, 0, 200, 0, 0, 400]


def test_a_chain_is_placed_as_a_whole_by_a_motif_in_a_later_phrase():
    # p2 has no motif of its own, but it shares p3's chain, so it moves down with p3
    score = score_of("p1 ltr: a:1 ^ #1[1 ^ 1]\np2 ltr: b:1\np3 ltr: ^2 c:1 #1[1 ^ 1]")

    assert [n.cents for n in score.notes] == [200, 400, 600, 0, 400, 400, 600]


def test_a_motif_first_heard_in_a_placed_chain_keeps_that_pitch_in_the_next():
    score = score_of(
        "p1 ltr: a:1 ^ #1[1 ^ 1]\np2 ltr: b:1 ^2 #1[1 ^ 1] ^ #3[1]\np3 ltr: c:1 ^ #3[1]"
    )

    assert [n.cents for n in score.notes] == [200, 400, 600, 0, 400, 600, 800, 600, 800]


def test_a_label_keeps_the_pitch_it_first_had_when_a_later_chain_disagrees():
    # p2 puts #2 a level off from p1, because #1 comes first there; p3 must still follow p1's #2
    score = score_of("p1 ltr: a:1 #1[1] ^ #2[1]\np2 ltr: b:1 #1[1] ^2 #2[1]\np3 ltr: c:1 ^ #2[1]")

    assert [n.cents for n in score.notes] == [0, 0, 200, 0, 0, 400, 0, 200]


# -- sections (rules 6 and 7): cents grow one section at a time


def test_a_rise_stays_a_rise_when_the_step_changes():
    score = build_score(parse_hymn("p1 ltr: a:2 ^ 2\np2 ltr: ^ b:2 ^ 2"), two_sections())

    assert [n.cents for n in score.notes] == [0, 200, 300, 400]
    assert [float(n.start) for n in score.notes] == [0, 1, 2, 2.5]
    assert [(float(s.start), float(s.end)) for s in score.sections] == [(0, 2), (2, 3)]
    assert score.notes[1].slides_on  # a join between sections still slides


def test_each_section_keeps_its_own_tempo_and_step():
    score = build_score(parse_hymn("p1 ltr: a:2 ^ 2\np2 ltr: ^ b:2 ^ 2"), two_sections())

    assert [(s.half_note_s, s.step_cents) for s in score.sections] == [(0.5, 200.0), (0.25, 100.0)]


def test_the_lowest_note_of_the_whole_hymn_is_the_base_even_in_a_later_section():
    # raw cents are 0, -200, then -100, -200 from the second section's origin at -200
    score = build_score(parse_hymn("p1 ltr: a:2 v 2\np2 ltr: ^ b:2 v 2"), two_sections())

    assert [n.cents for n in score.notes] == [200, 0, 100, 0]


def test_a_section_past_the_last_phrase_is_an_error():
    cfg = SynthSettings(
        seed=1,
        sections=(
            SynthSection(first_phrase=0, half_note_s=0.5, step_cents=200.0),
            SynthSection(first_phrase=5, half_note_s=0.5, step_cents=200.0),
        ),
    )

    with pytest.raises(SynthError, match="phrase 5"):
        build_score(parse_hymn("p1 ltr: a:2"), cfg)


# -- the highest pitch (rule 8)


def test_a_climb_out_of_range_fails_without_overflowing():
    with pytest.raises(SynthError, match="sample rate"):
        score_of("p1 ltr: a:1 ^99999999 1", step_cents=2400.0)


# 130 Hz up to half of 16 kHz is 7132 cents; this hymn's top is level 5 of 1200 cents
@pytest.mark.parametrize(
    "more, fits",
    [
        ({}, True),
        ({"base_hz": 300.0}, False),  # the ceiling comes down to 5684 cents
        ({"vibrato_width_cents": 2400.0}, False),  # half of it rides on the top note: 7200
        ({"drift_cents_per_min": 1200.0, "half_note_s": 30.0}, False),  # a minute of climbing adds 1200
        ({"drift_cents_per_min": -1200.0, "half_note_s": 30.0}, True),  # falling drift never raises the top
        (
            {"vibrato_width_cents": 2400.0, "drift_cents_per_min": -1200.0, "half_note_s": 30.0},
            False,  # and it doesn't make room for the vibrato either
        ),
        ({"vibrato_width_cents": 2400.0, "sample_rate_hz": 48000}, True),  # the ceiling goes up to 9034
    ],
    ids=[
        "as it is", "higher base", "wide vibrato", "rising drift", "falling drift", "falling drift gives no room",
        "higher sample rate",
    ],
)
def test_the_top_of_the_range_counts_the_base_the_vibrato_and_rising_drift(more, fits):
    if fits:
        assert len(score_of("p1 ltr: a:1 ^5 1", step_cents=1200.0, **more).notes) == 2
    else:
        with pytest.raises(SynthError, match="sample rate"):
            score_of("p1 ltr: a:1 ^5 1", step_cents=1200.0, **more)


# -- syllables (rule 9)


def test_the_first_note_must_start_a_syllable():
    for text in ("p1 ltr: 2", "p1 ltr: (a):2"):
        with pytest.raises(SynthError, match="syllable"):
            score_of(text)


# -- the edges of a phrase (rules 10 to 12)


def test_a_join_after_a_trailing_pause_does_not_slide():
    score = score_of("p1 ltr: a:2 .2\np2 ltr: ^ 2")

    assert [float(n.start) for n in score.notes] == [0, 2]
    assert score.end == 3
    assert [n.cause for n in score.notes] == ["syllable_start", "pitch_change"]
    assert [n.slides_on for n in score.notes] == [False, False]
    assert spans(score.rests) == [(1, 2)]


def test_an_equals_join_is_a_resung_note():
    score = score_of("p1 ltr: a:2\np2 ltr: = 2")

    assert [n.cause for n in score.notes] == ["syllable_start", "resung"]
    assert [n.syllable for n in score.notes] == [0, 0]
    assert [n.slides_on for n in score.notes] == [False, False]


def test_a_new_chain_with_no_lyric_keeps_the_syllable():
    score = score_of("p1 ltr: a:2\np2 ltr: 2")

    assert [n.cause for n in score.notes] == ["syllable_start", "resung"]
    assert [n.syllable for n in score.notes] == [0, 0]


def test_a_new_chain_on_another_level_is_a_pitch_change():
    score = score_of("p1 ltr: a:2 ^ 2\np2 ltr: 2")

    assert [n.cause for n in score.notes] == ["syllable_start", "pitch_change", "pitch_change"]
    assert [n.slides_on for n in score.notes] == [True, False, False]


def test_a_repeat_whose_body_ends_on_a_pause():
    score = score_of("p1 ltr: (a:1 .1)x2^ 1")

    assert [n.level for n in score.notes] == [0, 1, 1]
    assert [n.cause for n in score.notes] == ["syllable_start", "pitch_change", "resung"]
    assert [n.slides_on for n in score.notes] == [False, False, False]
    assert spans(score.rests) == [(0.5, 1), (1.5, 2)]
    assert [float(n.start) for n in score.notes] == [0, 1, 2]


def test_adjacent_pauses_are_one_rest():
    assert spans(score_of("p1 ltr: a:1 .2 .2 1").rests) == [(0.5, 2.5)]


def test_a_trailing_pause_counts_toward_the_end():
    score = score_of("p1 ltr: a:1 .2")

    assert spans(score.rests) == [(0.5, 1.5)]
    assert score.end == 1.5


def test_a_bare_tick_is_a_resung_note():
    score = score_of("p1 ltr: a:1 ! 1")

    assert [n.cause for n in score.notes] == ["syllable_start", "resung"]
    assert [n.slides_on for n in score.notes] == [False, False]


def test_a_new_syllable_on_the_same_level_is_a_syllable_start():
    assert [n.cause for n in score_of("p1 ltr: a:1 b:1").notes] == ["syllable_start", "syllable_start"]


def test_a_vowel_label_does_not_start_a_syllable():
    score = score_of("p1 ltr: a:1 (a):1")

    assert [n.syllable for n in score.notes] == [0, 0]
    assert [n.cause for n in score.notes] == ["syllable_start", "resung"]


@pytest.mark.parametrize(
    "join, slides",
    [("^ ", True), ("v2 ", True), ("!^ ", False), ("!v2 ", False), ("! ", False), ("= ", False), ("", False)],
    ids=["up", "down two", "abrupt up", "abrupt down two", "tick", "equals", "no join"],
)
def test_only_a_smooth_join_slides_into_the_next_phrase(join, slides):
    notes = score_of(f"p1 ltr: a:2\np2 ltr: {join}2").notes

    assert [n.slides_on for n in notes] == [slides, False]


def test_a_repeat_on_one_level_is_re_sung_with_no_slide():
    score = score_of("p1 ltr: (a:1)x3")

    assert [n.cause for n in score.notes] == ["syllable_start", "resung", "resung"]
    assert [n.slides_on for n in score.notes] == [False, False, False]
    assert [float(n.start) for n in score.notes] == [0, 0.5, 1]


def test_a_fast_group_slides_between_its_notes():
    score = score_of("p1 ltr: >2{a:* ^ b:* v c:*}")

    assert [n.kind for n in score.notes] == ["fast", "fast", "fast"]
    assert [n.syllable for n in score.notes] == [0, 1, 2]
    assert [n.slides_on for n in score.notes] == [True, True, False]


# -- the number of samples (rule 17)


def test_the_demo_is_eleven_seconds_of_samples():
    assert sample_count(score_of(DEMO), settings()) == 176000


def test_the_echo_tail_adds_its_own_samples():
    cfg = settings(echo_rt60_s=0.5)

    assert sample_count(build_score(parse_hymn(DEMO), cfg), cfg) == 176000 + 8000


def test_samples_are_counted_exactly_not_in_floating_point():
    # 0.1 is stored a hair above a tenth, so exactly 0.1 s at 16 kHz is a hair over sample 1600
    cfg = settings(half_note_s=0.1)

    assert sample_count(build_score(parse_hymn("p1 ltr: a:1"), cfg), cfg) == 1601


def test_an_echo_tail_is_counted_exactly_too():
    cfg = settings(echo_rt60_s=0.1)

    assert sample_count(build_score(parse_hymn("p1 ltr: a:2"), cfg), cfg) == 16000 + 1601


def test_the_random_sources_and_the_limit_have_their_fixed_values():
    assert (TIMING, NOISE, ECHO, CYMBALS, MAX_SECONDS) == (0, 1, 2, 3, 1800)
