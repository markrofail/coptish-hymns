import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from hymnstring.notation import (
    Hymn,
    hymn_unit,
    parse_hymn,
    parse_line,
    render_hymn,
    render_phrase,
)

DEMO = (
    "{id} {direction}: #1[A:2 ^ 1 v 1] ^ lē:~2 .2 v (lou:1)x3^ >1{{i:*}} a:2 !v2 "
    "#1[(a):2 ^ 1 v 1] v 4"
)
BEAD_XS = [40, 65, 77.5, 90, 140, 152.5, 165, 177.5, 190, 215, 240, 252.5, 265]
BEAD_LEVELS = [1, 2, 1, 2, 1, 2, 3, 3, 3, 1, 2, 1, 0]
TEAL, PURPLE, ORANGE = "#1D9E75", "#7F77DD", "#D85A30"
FIXTURES = Path(__file__).parent.parent / "fixtures" / "render"


def draw(text, direction="ltr", **options):
    return ET.fromstring(render_phrase(parse_line(f"p1 {direction}: {text}"), **options))


def demo(direction="ltr"):
    return ET.fromstring(render_phrase(parse_line(DEMO.format(id="p1", direction=direction))))


def find(root, name):
    return [element for element in root.iter() if element.get("class") == name]


def numbers(path):
    return [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", path.get("d"))]


def beads(root):
    return [(float(b.get("cx")), float(b.get("cy"))) for b in find(root, "bead")]


def words(element):
    return "".join(element.itertext())


# --- the demo phrase -------------------------------------------------------


def test_demo_beads_sit_at_hand_derived_positions_and_levels():
    placed = beads(demo())
    bottom = placed[-1][1]

    assert [x for x, _ in placed] == BEAD_XS
    assert [bottom - y for _, y in placed] == [20 * level for level in BEAD_LEVELS]


def test_demo_canvas_puts_the_highest_label_12_from_the_top_and_the_lyrics_28_below_level_0():
    root = demo()

    # Level 3 is at y 54, so the repeat label's top, 42 above that, is at 12.
    assert beads(root)[-1][1] == 114
    assert root.get("viewBox") == "0 0 355 156"
    assert (root.get("width"), root.get("height")) == ("710", "312")
    assert [float(t.get("y")) for t in find(root, "lyric")] == [142] * 5
    assert root.get("role") == "img"
    assert words(root.find("{http://www.w3.org/2000/svg}title")) == "Phrase p1"


def test_demo_mirrored_has_the_same_width_and_every_bead_at_width_minus_x():
    root = demo("rtl")

    assert root.get("viewBox") == "0 0 355 156"
    assert [x for x, _ in beads(root)] == [355 - x for x in BEAD_XS]


def test_demo_has_two_motif_labels_one_repeat_with_its_bracket_and_one_breath():
    root = demo()

    assert [words(t) for t in find(root, "motif-label")] == ["①", "①"]
    assert [(float(t.get("x")), float(t.get("y"))) for t in find(root, "motif-label")] == [
        (65, 62),
        (240, 62),
    ]
    assert [words(t) for t in find(root, "repeat-label")] == ["×3 ↗"]
    (label,) = find(root, "repeat-label")
    assert (float(label.get("x")), float(label.get("y"))) == (158.75, 24)
    (bracket,) = find(root, "repeat-bracket")
    # Event 7 is the last copy; event 8 (i) starts at 177.5.
    assert numbers(bracket) == [140, 38, 140, 32, 177.5, 32, 177.5, 38]
    (breath,) = find(root, "breath")
    dot = breath.find("{http://www.w3.org/2000/svg}circle")
    assert (float(dot.get("cx")), float(dot.get("cy")), float(dot.get("r"))) == (127.5, 58, 2.5)


def test_demo_lyrics_are_on_their_beads_and_only_i_is_underlined():
    root = demo()
    lyrics = find(root, "lyric")

    assert [words(t) for t in lyrics] == ["A", "lē", "lou", "i", "a"]
    assert [float(t.get("x")) for t in lyrics] == [BEAD_XS[i] for i in (0, 3, 4, 7, 8)]
    assert [t.get("text-decoration") for t in lyrics] == [None, None, None, "underline", None]
    (vowel,) = find(root, "vowel")
    assert (words(vowel), float(vowel.get("x"))) == ("(a)", BEAD_XS[9])


def test_demo_moves_are_teal_into_and_out_of_a_motif_and_purple_inside_it():
    root = demo()
    moves = [e for e in root.iter() if e.get("class") in ("slope", "corner")]

    assert [e.get("stroke") for e in moves] == [
        PURPLE, PURPLE, TEAL, TEAL, TEAL, TEAL, TEAL, PURPLE, PURPLE, TEAL,
    ]
    assert [e.get("class") for e in moves].count("corner") == 1
    assert len(find(root, "tick")) == 0


def test_demo_draws_one_wave_one_fast_one_pause_and_one_corner():
    root = demo()

    assert [len(find(root, name)) for name in ("wave", "fast", "pause", "corner", "tick")] == [
        1, 1, 1, 1, 0,
    ]
    (wave,) = find(root, "wave")
    # Eight half-waves of 3 fit in 25; then a line to the end of the stretch.
    assert wave.get("d").startswith("M90 74 Q91.5 67 93 74 T96 74 T99 74")
    assert wave.get("d").endswith("T114 74 L115 74")
    (fast,) = find(root, "fast")
    assert (fast.get("stroke-width"), fast.get("stroke-dasharray"), fast.get("stroke-linecap")) == (
        "1.5", "3 2.5", "butt",
    )
    (pause,) = find(root, "pause")
    assert (pause.get("stroke"), pause.get("stroke-dasharray")) == ("#888780", "0.5 4")


def test_demo_beads_take_the_innermost_motif_colour():
    fills = [b.get("fill") for b in find(demo(), "bead")]

    assert fills == [PURPLE] * 3 + [TEAL] * 6 + [PURPLE] * 3 + [TEAL]


# --- proportions and small cases -------------------------------------------


@pytest.mark.parametrize(
    "text, lengths",
    [
        ("1 ^ 2 v 3 4", [1, 2, 3]),
        ("4 2 !^ 6 v 2 1", [4, 2, 6, 2]),
        ("~2 ^ 5 ! 3 .2 ", [2, 5]),
        (">4{* ^ * v * ^ *} 2", [1, 1, 1, 1]),
    ],
)
@pytest.mark.parametrize("unit", [8, 12.5, 20])
def test_bead_gaps_are_the_note_lengths_times_one_unit(text, lengths, unit):
    xs = [x for x, _ in beads(draw(text, unit=unit))]
    gaps = [b - a for a, b in zip(xs, xs[1:])]

    assert len(gaps) >= len(lengths) - 1
    for gap, length in zip(gaps, lengths):
        assert gap == pytest.approx(length * unit, abs=0.01)


def test_a_bare_bang_draws_one_tick_across_the_string():
    root = draw("2 ! 2")
    (tick,) = find(root, "tick")

    x, top, x2, bottom = numbers(tick)
    assert (x, x2, bottom - top) == (65, 65, 12)
    assert tick.get("stroke-width") == "1.5"
    assert [b[1] for b in beads(root)] == [top + 6, top + 6]


def test_the_same_motif_keeps_its_colour_when_shifted_and_the_second_label_takes_the_second_colour():
    shifted = draw("#1[2 ^ 1] #1+1[2 ^ 1]")
    other = draw("#2[1]")

    assert [words(t) for t in find(shifted, "motif-label")] == ["①", "①+1"]
    assert {b.get("fill") for b in find(shifted, "bead")} == {PURPLE}
    assert [b.get("fill") for b in find(other, "bead")] == [ORANGE]
    assert [words(t) for t in find(draw("#21[1] #3-2[1]"), "motif-label")] == ["#21", "③-2"]


def test_repeat_labels_name_the_step_and_mirror_the_arrows():
    def label(text, direction="ltr"):
        return [words(t) for t in find(draw(text, direction), "repeat-label")]

    assert label("(1)x3") == ["×3"]
    assert label("(1)x3v") == ["×3 ↘"]
    assert label("(1)x3^2") == ["×3 ↗2"]
    assert label("(1)x3v2") == ["×3 ↘2"]
    assert label("(1)x3^", "rtl") == ["×3 ↖"]
    assert label("(1)x3v2", "rtl") == ["×3 ↙2"]


def test_added_and_silent_letters_are_coloured_spans_in_reading_order():
    root = draw("ⲧ<+ⲉ>ⲛ:2 <-ϩ>ⲁ:2")
    first, second = find(root, "lyric")
    spans = lambda text: [(s.get("fill"), words(s)) for s in text]

    assert words(first) == "ⲧⲉⲛ" and spans(first) == [("#C8402A", "ⲉ")]
    assert words(second) == "ϩⲁ" and spans(second) == [("#A3A29C", "ϩ")]


def test_a_phrase_join_draws_nothing():
    plain = render_phrase(parse_line("p2 ltr: 1 ^ 2"))
    joined = render_phrase(parse_line("p2 ltr: v2 1 ^ 2"))

    assert joined == plain


# --- the five review-focus cases -------------------------------------------


def test_slopes_in_very_short_stretches_never_run_backwards_past_the_bead_they_leave():
    text = ">1{* ^ * ^ * ^ *}"
    left_to_right = draw(text)
    right_to_left = draw(text, "rtl")
    xs = [x for x, _ in beads(left_to_right)]

    slopes = find(left_to_right, "slope")
    assert len(slopes) == 3
    for index, slope in enumerate(slopes):
        values = numbers(slope)[0::2]
        assert values == sorted(values)
        assert values[0] >= xs[index]
        assert values[-1] == xs[index + 1]
    for slope in find(right_to_left, "slope"):
        values = numbers(slope)[0::2]
        assert values == sorted(values, reverse=True)


def test_pauses_at_the_edges_end_the_string_or_hand_over_to_a_move():
    ending = draw("1 .2")
    (pause,) = find(ending, "pause")
    assert ending.get("viewBox").split()[2] == "117.5"
    assert numbers(pause)[0::2] == [52.5, 77.5]
    assert len(find(ending, "breath")) == 1

    moving = draw("1 .2 v 1")
    (pause,) = find(moving, "pause")
    (slope,) = find(moving, "slope")
    # The pause stops 6 short of the next bead and the slope takes over.
    assert numbers(pause)[0::2] == [52.5, 71.5]
    assert numbers(slope)[0::2] == [71.5, 74.5, 74.5, 77.5]
    assert numbers(pause)[1] == numbers(slope)[1] == numbers(slope)[3]


JINKIM = "ⲧ̅ⲓ:* ^ ⲛⲉ:* v ⲣⲁ:*"


def box_widths(root):
    return [0.62 * 14 * len(words(t).replace("̅", "")) for t in find(root, "lyric")]


@pytest.mark.parametrize("fast", [">2{ⲧⲓ:* ^ ⲛⲉ:* v ⲣⲁ:*}", ">2{" + JINKIM + "}"])
def test_crowded_lyrics_do_not_overlap_and_a_combining_mark_has_no_width(fast):
    phrase = parse_line(f"p1 ltr: {fast}")
    unit = hymn_unit(Hymn((phrase,)))
    root = ET.fromstring(render_phrase(phrase, unit=unit))
    xs = [float(t.get("x")) for t in find(root, "lyric")]

    assert unit > 12.5
    assert unit == 30.54  # (0.62 * 14 * 2 + 3) / (2/3), rounded up
    for width, left, right in zip(box_widths(root), xs, xs[1:]):
        assert right - left >= width + 3 - 1e-6


def boxes(root):
    # Real extents, worked out here from the drawn marks and not from the renderer's rules.
    found = []
    for mark in find(root, "breath"):
        dot = mark.find("{http://www.w3.org/2000/svg}circle")
        cx, cy = float(dot.get("cx")), float(dot.get("cy"))
        found.append((cx - 2.5, cx + 3, cy - 2.5, cy + 8.5))
    for label in find(root, "motif-label") + find(root, "repeat-label"):
        x, y = float(label.get("x")), float(label.get("y"))
        half = 0.62 * 12 * len(words(label)) / 2
        found.append((x - half, x + half, y - 9, y + 3))
    for bracket in find(root, "repeat-bracket"):
        xs, ys = numbers(bracket)[0::2], numbers(bracket)[1::2]
        found.append((min(xs), max(xs), min(ys), max(ys)))
    return found


@pytest.mark.parametrize("text", ["#1[(1)x3 ^ 2]", "(#1[1 ^ 1])x2", "(#1[1 ^ 1] .2)x2 #1[1]"])
def test_annotations_never_overlap(text):
    root = draw(text)
    found = boxes(root)

    assert len(found) >= 3
    for index, (l1, r1, t1, b1) in enumerate(found):
        for l2, r2, t2, b2 in found[index + 1:]:
            assert r1 <= l2 or r2 <= l1 or b1 <= t2 or b2 <= t1
    assert 12 <= min(top for _, _, top, _ in found) <= 15  # label glyphs sit 3 below the box


def test_a_repeat_over_a_motif_stacks_above_it():
    root = draw("#1[(1)x3 ^ 2]")
    (motif,) = find(root, "motif-label")
    (repeat,) = find(root, "repeat-label")

    assert float(repeat.get("y")) < float(motif.get("y")) - 12


def test_right_to_left_mirrors_the_geometry_but_not_the_letters():
    root = draw("آ:2 ^ مين:2", "rtl")
    first, second = find(root, "lyric")

    assert [words(first), words(second)] == ["آ", "مين"]
    assert (first.get("text-anchor"), first.get("direction")) == ("end", "rtl")
    width = float(root.get("viewBox").split()[2])
    assert [x for x, _ in beads(root)] == pytest.approx([width - 40, width - 65], abs=0.01)
    assert float(first.get("x")) > float(second.get("x"))
    # The last lyric reaches left to the margin and no further.
    assert float(second.get("x")) - 0.62 * 14 * 3 == pytest.approx(40, abs=0.01)


# --- units and pages -------------------------------------------------------


def test_the_demo_stays_at_exactly_a_half_note_of_12_5():
    hymn = parse_hymn(DEMO.format(id="p1", direction="ltr"))

    assert hymn_unit(hymn) == 12.5


def test_a_hymn_page_draws_every_phrase_with_the_hymns_unit():
    hymn = parse_hymn("p1 ltr: 2 ^ 2\np2 ltr: >2{ⲧⲓ:* ^ ⲛⲉ:* v ⲣⲁ:*}")
    page = render_hymn(hymn)
    drawings = [ET.fromstring(m) for m in re.findall(r"<svg.*?</svg>", page, re.S)]
    first, second = (beads(d) for d in drawings)

    assert page.startswith("<!doctype html>")
    assert hymn_unit(hymn) == 30.54
    assert first[1][0] - first[0][0] == pytest.approx(2 * 30.54, abs=0.01)
    assert second[1][0] - second[0][0] == pytest.approx(30.54 * 2 / 3, abs=0.01)


# --- snapshots -------------------------------------------------------------

RULES = [
    "1 ^ 1 ^ 2",
    "1 ^ 2 ^ 4",
    "2 2",
    "2 ^ 2 v 2 ^3 2",
    "2 !v2 2 ! 2",
    "~2 ^ ~4",
    "2 .2 2 .4 2",
    ">1{i:*} ^ >2{ⲧⲓ:* ^ ⲛⲉ:* v ⲣⲁ:*}",
    "(1)x3 ^ (1)x3^ (1)x3v",
    "#1[2 ^ 1] v 2 #1[ⲡⲉ:2 ^ 1]",
    "#1[2 ^ 1] #1+1[2 ^ 1] v3 #1-1[2 ^ 1]",
    "ⲁ:2 ^ 2 v (ⲁ):4",
    "ⲧ<+ⲉ>ⲛ:2 <-ϩ>ⲁ:2",
    "v2 1 ^ 2",
]


def check_snapshot(name, actual):
    path = FIXTURES / name
    if os.environ.get("REFRESH_SNAPSHOTS"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(actual, encoding="utf-8")
    assert path.exists(), f"{path} is missing; run with REFRESH_SNAPSHOTS=1 to write it"
    assert actual == path.read_text(encoding="utf-8")


def test_demo_snapshots():
    for direction, name in (("ltr", "demo.svg"), ("rtl", "demo_rtl.svg")):
        check_snapshot(name, render_phrase(parse_line(DEMO.format(id="p1", direction=direction))))


def test_every_rule_example_page_snapshot():
    lines = [f"p{n} ltr: {text}" for n, text in enumerate(RULES, 1)]
    lines.append("p15 rtl: آ:2 ^ مين:2")
    check_snapshot("rules.html", render_hymn(parse_hymn("\n".join(lines))))


# --- repeat feet clear of the string around the repeat ----------------------


@pytest.mark.parametrize(
    "text, left, right, bead",
    [
        ("(1)x3 ^ 1", 40, 77.5, 3),  # the string climbs to the next note at the right foot
        ("1 !v3 (1)x2", 52.5, 77.5, 0),  # a corner drops onto the first note at the left foot
        ("1 ^ (1)x2 v 1", 52.5, 77.5, 1),  # a lower note after it changes nothing
    ],
)
def test_a_repeat_bracket_clears_the_string_beside_it(text, left, right, bead):
    root = draw(text)
    (bracket,) = find(root, "repeat-bracket")
    highest = beads(root)[bead][1]  # the highest level beside the repeat

    assert numbers(bracket) == [left, highest - 16, left, highest - 22, right, highest - 22, right, highest - 16]
