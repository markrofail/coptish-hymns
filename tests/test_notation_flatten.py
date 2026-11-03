import subprocess
import sys
from fractions import Fraction
from pathlib import Path

from hymnstring.notation import Move, parse_hymn, parse_line
from hymnstring.notation.flatten import FlatNote, FlatPause, MotifUse, RepeatUse, flatten, walk_chains

DEMO = (
    "p1 ltr: #1[A:2 ^ 1 v 1] ^ lē:~2 .2 v (lou:1)x3^ >1{i:*} a:2 !v2 "
    "#1[(a):2 ^ 1 v 1] v 4"
)


def flat(text, start_level=0):
    return flatten(parse_line("p1 ltr: " + text).items, start_level)


def levels(result):
    return [event.level for event in result.events]


def note_levels(result):
    return [event.level for event in result.events if isinstance(event, FlatNote)]


def test_demo_levels_and_lengths_once_the_lowest_note_is_zero():
    result = flatten(parse_line(DEMO).items)
    lowest = min(event.level for event in result.events if isinstance(event, FlatNote))

    shifted = [
        None if isinstance(e, FlatPause) else e.level - lowest for e in result.events
    ]

    assert shifted == [1, 2, 1, 2, None, 1, 2, 3, 3, 3, 1, 2, 1, 0]
    assert [e.length for e in result.events] == [2, 1, 1, 2, 2, 1, 1, 1, 1, 2, 2, 1, 1, 4]
    assert sum(isinstance(e, FlatNote) for e in result.events) == 13
    assert sum(e.length for e in result.events) == 22


def test_demo_ends_one_level_below_where_it_started():
    assert flatten(parse_line(DEMO).items).end_level == -1


def test_a_repeat_with_a_step_up_climbs_and_keeps_the_lyric_on_the_first_copy_only():
    result = flat("(lou:1)x3^")
    lyrics = [event.lyric for event in result.events]

    assert note_levels(result) == [0, 1, 2]
    assert lyrics[0] is not None and lyrics[1:] == [None, None]


def test_a_same_level_repeat_has_no_moves():
    result = flat("(1)x3")

    assert note_levels(result) == [0, 0, 0]
    assert [e.move for e in result.events] == [None, None, None]


def test_a_repeat_stepping_down_two_levels():
    assert note_levels(flat("(1)x3v2")) == [0, -2, -4]


def test_a_repeat_join_is_a_smooth_move_of_the_size_needed():
    result = flat("(1 ^ 1)x2")

    assert note_levels(result) == [0, 1, 0, 1]
    assert [e.move for e in result.events] == [None, Move(False, 1), Move(False, -1), Move(False, 1)]


def test_copies_that_start_where_the_last_ended_have_no_join_move():
    result = flat("(1 ^ 1)x3^")

    assert note_levels(result) == [0, 1, 1, 2, 2, 3]
    assert [e.move for e in result.events] == [
        None, Move(False, 1), None, Move(False, 1), None, Move(False, 1),
    ]


def test_a_pause_holds_the_level_and_the_next_move_comes_after_it():
    result = flat("(1 .1)x2^")

    assert [(type(e).__name__, e.level) for e in result.events] == [
        ("FlatNote", 0), ("FlatPause", 0), ("FlatNote", 1), ("FlatPause", 1),
    ]
    # the first copy ends on the pause at level 0, so the join up carries into copy two's note
    assert result.events[2].move == Move(False, 1)


def test_a_fast_group_splits_its_length_evenly():
    result = flat(">2{* ^ * v *}")

    assert note_levels(result) == [0, 1, 0]
    assert [e.length for e in result.events] == [Fraction(2, 3)] * 3
    assert [e.kind for e in result.events] == ["fast"] * 3
    assert [e.move for e in result.events] == [None, Move(False, 1), Move(False, -1)]


def test_a_bare_abrupt_move_keeps_the_level_and_is_recorded():
    result = flat("1 ! 1")

    assert note_levels(result) == [0, 0]
    assert result.events[1].move == Move(True, 0)


def test_a_vibrato_note_has_its_own_kind():
    assert [e.kind for e in flat("~2 ^ 1").events] == ["vibrato", "note"]


def test_start_level_moves_everything():
    result = flat("1 ^ 1", start_level=5)

    assert note_levels(result) == [5, 6]
    assert result.end_level == 6


def test_a_trailing_pause_ends_on_the_level_it_held():
    assert flat("1 ^ 1 .2").end_level == 1


def test_motifs_are_listed_in_order_with_start_level_and_shape():
    result = flat("#1[2 ^ 1] v #1+1[(1)x2 ^ 1]")

    assert result.motifs == (
        MotifUse(1, 0, 0, ((None, "note", Fraction(2)), (Move(False, 1), "note", Fraction(1))), 0, 2),
        MotifUse(
            1, 1, 0,
            (
                (None, "note", Fraction(1)),
                (None, "note", Fraction(1)),
                (Move(False, 1), "note", Fraction(1)),
            ),
            2,
            5,
        ),
    )


def test_a_motif_in_a_repeat_has_one_use_per_copy_and_the_join_is_not_in_the_shape():
    result = flat("(#1[1 ^ 1])x2^")

    assert [m.start_level for m in result.motifs] == [0, 1]
    assert result.motifs[0].shape == result.motifs[1].shape
    assert result.motifs[1].shape == ((None, "note", Fraction(1)), (Move(False, 1), "note", Fraction(1)))


def test_the_shape_includes_pauses_and_ignores_lyrics():
    result = flat("#1[a:1 .2 ^ 3]")

    assert result.motifs[0].shape == (
        (None, "note", Fraction(1)),
        (None, "pause", Fraction(2)),
        (Move(False, 1), "note", Fraction(3)),
    )


def test_flatten_and_its_types_are_exported_from_the_package():
    import hymnstring.notation as notation

    for name in ("flatten", "Flat", "FlatNote", "FlatPause", "FlatEvent", "MotifUse", "ChainedPhrase", "walk_chains"):
        assert name in notation.__all__
        assert hasattr(notation, name)


def test_demo_spans_cover_the_events_of_each_motif_and_repeat():
    result = flatten(parse_line(DEMO).items)

    assert [(m.first_event, m.end_event) for m in result.motifs] == [(0, 3), (10, 13)]
    assert result.repeats == (RepeatUse(3, 1, 5, 8),)


def test_a_repeat_around_motifs_spans_all_its_copies_and_each_copy_has_its_own_motif_span():
    result = flat("(#1[1 ^ 1])x2")

    assert [(m.first_event, m.end_event) for m in result.motifs] == [(0, 2), (2, 4)]
    assert result.repeats == (RepeatUse(2, 0, 0, 4),)


def test_a_repeat_inside_a_repeat_appears_once_per_outer_copy_and_outer_comes_first():
    result = flat("((1)x2 ^ 1)x2")

    assert result.repeats == (
        RepeatUse(2, 0, 0, 6),
        RepeatUse(2, 0, 0, 2),
        RepeatUse(2, 0, 3, 5),
    )


def test_chains_share_levels_through_joins():
    hymn = parse_hymn("p1 ltr: 1 ^ 1\np2 ltr: v2 1\np3 ltr: = 1\np4 ltr: 1")

    walked = list(walk_chains(hymn))

    assert [w.chain for w in walked] == [0, 0, 0, 1]
    assert [[e.level for e in w.flat.events] for w in walked] == [[0, 1], [-1], [-1], [0]]
    assert [w.index for w in walked] == [0, 1, 2, 3]


def test_a_trailing_pause_holds_the_level_a_join_starts_from():
    hymn = parse_hymn("p1 ltr: 1 ^ 1 .2\np2 ltr: ^ 1")

    assert [w.flat.events[-1].level for w in walk_chains(hymn)] == [1, 2]


def test_the_first_phrase_starts_at_level_0_whatever_its_join():
    hymn = parse_hymn("p1 ltr: ^ 1")

    assert [w.flat.events[0].level for w in walk_chains(hymn)] == [0]


def test_a_phrase_can_be_walked_with_other_items():
    hymn = parse_hymn("p1 ltr: 1 ^ 1 ^ 1\np2 ltr: ^ 1")

    walked = walk_chains(hymn, items_of=lambda phrase: phrase.items[:3])  # without the last move and note

    assert [[e.level for e in w.flat.events] for w in walked] == [[0, 1], [2]]


def test_the_notation_package_imports_neither_contracts_nor_synth_nor_numpy():
    # in a process of its own, since this one may have loaded all three already
    code = (
        "import sys\n"
        "import hymnstring.notation\n"
        "banned = ('numpy', 'hymnstring.contracts', 'hymnstring.synth')\n"
        "print(sorted(name for name in banned if name in sys.modules))\n"
    )
    done = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=20,
        cwd=Path(__file__).parents[1],
    )

    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "[]"
