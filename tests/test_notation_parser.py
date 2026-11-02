import random
import re
import subprocess
import sys
from pathlib import Path

import pytest

from hymnstring.notation import (
    Bead,
    Fast,
    Hymn,
    Letters,
    Motif,
    Move,
    NotationError,
    Note,
    Pause,
    Phrase,
    Repeat,
    SameLevel,
    Syllable,
    Vowel,
    parse_hymn,
    parse_line,
    validate,
    write_hymn,
    write_line,
)

SPEC = Path(__file__).parents[1] / "hymnstring" / "notation" / "SPEC.md"
HAS_PREFIX = re.compile(r"^p\d+ (ltr|rtl): ")


def syl(text, mark="plain"):
    return Syllable((Letters(text, mark),))


def line(items, join=None, phrase_id="p1", direction="ltr"):
    return Phrase(phrase_id, direction, join, tuple(items))


def spec_examples():
    section = SPEC.read_text(encoding="utf-8").split("## One example for each rule")[1]
    section = section.split("\n## ")[0]
    found = []
    for row in section.splitlines():
        cell = re.match(r"^\|[^|]*\|\s*`(.+?)`\s*\|", row)
        if cell:
            text = cell.group(1)
            found.append(text if HAS_PREFIX.match(text) else "p1 ltr: " + text)
    return found


def spec_demo():
    return re.search(r"^p1 ltr: #1\[A:2.*$", SPEC.read_text(encoding="utf-8"), re.M).group(0)


def test_the_harvest_finds_the_examples():
    assert len(spec_examples()) >= 14


@pytest.mark.parametrize("text", spec_examples() + [spec_demo()])
def test_canonical_text_survives_parse_then_write(text):
    assert write_line(parse_line(text)) == text


@pytest.mark.parametrize("text", spec_examples())
def test_every_spec_example_is_valid(text):
    # the join and p2 examples are read after a first phrase
    hymn = text if text.startswith("p1 ") else "p1 ltr: 2\n" + text

    assert validate(parse_hymn(hymn)) == []


@pytest.mark.parametrize("text", ["p1 ltr: ~1", "p1 ltr: .1"])
def test_half_length_vibratos_and_pauses_survive_parse_then_write(text):
    assert write_line(parse_line(text)) == text


PARSES = [
    ("p1 ltr: 2", line([Note(2)])),
    ("p3 rtl: 1", line([Note(1)], phrase_id="p3", direction="rtl")),
    ("p1 ltr: ~4", line([Note(4, True)])),
    ("p1 ltr: lē:~2", line([Note(2, True, syl("lē"))])),
    ("p1 ltr: ϣⲁ:3", line([Note(3, lyric=syl("ϣⲁ"))])),
    ("p1 ltr: (a):2", line([Note(2, lyric=Vowel("a"))])),
    ("p1 ltr: 1 .2 1", line([Note(1), Pause(2), Note(1)])),
    ("p1 ltr: 1 ^ 1 v2 1", line([Note(1), Move(False, 1), Note(1), Move(False, -2), Note(1)])),
    ("p1 ltr: 1 ! 1", line([Note(1), Move(True, 0), Note(1)])),
    ("p1 ltr: 1 !v2 1 !^ 1", line([Note(1), Move(True, -2), Note(1), Move(True, 1), Note(1)])),
    ("p2 ltr: v2 1", line([Note(1)], Move(False, -2), "p2")),
    ("p2 ltr: ! 1", line([Note(1)], Move(True, 0), "p2")),
    ("p2 ltr: = 1", line([Note(1)], SameLevel(), "p2")),
    ("p1 ltr: ^ ^ 1", line([Move(False, 1), Note(1)], Move(False, 1))),
    ("p1 ltr: 1 ^", line([Note(1), Move(False, 1)])),
    ("p1 ltr: (1)x1", line([Repeat((Note(1),), 1)])),
    ("p1 ltr: (1)x3", line([Repeat((Note(1),), 3, 0)])),
    ("p1 ltr: (lou:1)x3^", line([Repeat((Note(1, lyric=syl("lou")),), 3, 1)])),
    ("p1 ltr: (1)x3v2", line([Repeat((Note(1),), 3, -2)])),
    ("p1 ltr: (1)x3^2 5", line([Repeat((Note(1),), 3, 2), Note(5)])),
    ("p1 ltr: (1)x3^ 2", line([Repeat((Note(1),), 3, 1), Note(2)])),
    ("p1 ltr: (1)x10000", line([Repeat((Note(1),), 10000)])),
    ("a_b-C9 ltr: 1", line([Note(1)], phrase_id="a_b-C9")),
    ("p1 ltr: (1 ^ 1)x2", line([Repeat((Note(1), Move(False, 1), Note(1)), 2)])),
    ("p1 ltr: (^ 1)x2", line([Repeat((Move(False, 1), Note(1)), 2)])),
    ("p1 ltr: ((1)x2 ^ 1)x3", line([Repeat((Repeat((Note(1),), 2), Move(False, 1), Note(1)), 3)])),
    ("p1 ltr: >1{i:*}", line([Fast(1, (Bead(syl("i")),))])),
    ("p1 ltr: >1{* ! *}", line([Fast(1, (Bead(), Move(True, 0), Bead()))])),
    ("p1 ltr: >1{* *}", line([Fast(1, (Bead(), Bead()))])),
    (
        "p1 ltr: >2{ⲧⲓ:* ^ * !v2 (a):*}",
        line([Fast(2, (Bead(syl("ⲧⲓ")), Move(False, 1), Bead(), Move(True, -2), Bead(Vowel("a"))))]),
    ),
    ("p1 ltr: #1[2 ^ 1]", line([Motif(1, 0, (Note(2), Move(False, 1), Note(1)))])),
    ("p1 ltr: #1+1[1]", line([Motif(1, 1, (Note(1),))])),
    ("p1 ltr: #1-2[1]", line([Motif(1, -2, (Note(1),))])),
    ("p1 ltr: #12[1]", line([Motif(12, 0, (Note(1),))])),
    (
        "p1 ltr: #1[a:2 ^ >1{i:*}] v [...]#1",
        line([
            Motif(1, 0, (Note(2, lyric=syl("a")), Move(False, 1), Fast(1, (Bead(syl("i")),))))
            , Move(False, -1),
            Motif(1, 0, (Note(2), Move(False, 1), Fast(1, (Bead(),)))),
        ]),
    ),
    (
        "p1 ltr: #1[(1)x3^ 2] v [...]#1",
        line([
            Motif(1, 0, (Repeat((Note(1),), 3, 1), Note(2))),
            Move(False, -1),
            Motif(1, 0, (Repeat((Note(1),), 3, 1), Note(2))),
        ]),
    ),
    (
        "p1 ltr: #1+1[a:2] v #1[a:2] [...]#1",
        line([
            Motif(1, 1, (Note(2, lyric=syl("a")),)),
            Move(False, -1),
            Motif(1, 0, (Note(2, lyric=syl("a")),)),
            Motif(1, 0, (Note(2),)),
        ]),
    ),
]


@pytest.mark.parametrize("text, expected", PARSES)
def test_parse_line_gives_the_model(text, expected):
    assert parse_line(text) == expected


def test_parse_hymn_gives_phrases_in_order():
    assert parse_hymn("p1 ltr: 1\np2 rtl: = 2") == Hymn(
        (line([Note(1)]), line([Note(2)], SameLevel(), "p2", "rtl"))
    )


def test_motif_copies_resolve_across_phrases_in_order():
    hymn = parse_hymn("p1 ltr: #1[a:2 ^ 1]\np2 ltr: v [...]#1\np3 ltr: #2[3] [...]#2 [...]#1")
    assert hymn.phrases[1].items == (Motif(1, 0, (Note(2), Move(False, 1), Note(1))),)
    assert hymn.phrases[2].items == (
        Motif(2, 0, (Note(3),)),
        Motif(2, 0, (Note(3),)),
        Motif(1, 0, (Note(2), Move(False, 1), Note(1))),
    )
    assert hymn.phrases[1].join == Move(False, -1)


def test_parse_line_copies_resolve_only_within_the_line():
    assert parse_hymn("p1 ltr: #1[2]\np2 ltr: [...]#1").phrases[1].items == (Motif(1, 0, (Note(2),)),)
    with pytest.raises(NotationError):
        parse_line("p2 ltr: [...]#1")
    assert parse_line("p2 ltr: #1[2] [...]#1").items[1] == Motif(1, 0, (Note(2),))


def test_a_copy_before_any_occurrence_is_rejected_in_a_hymn_too():
    with pytest.raises(NotationError):
        parse_hymn("p1 ltr: [...]#1\np2 ltr: #1[2]")


ALIASES = [
    (
        "p1 ltr: ①[A:2 ↑ 1 ↓ 1] ↑ lē:~ . ↓ (lou:1)×3↗ →1{i:•} a:2 ↝↓2 ①[(a):2 ↑ 1 ↓ 1] ↓ 4",
        "p1 ltr: #1[A:2 ^ 1 v 1] ^ lē:~2 .2 v (lou:1)x3^ >1{i:*} a:2 !v2 #1[(a):2 ^ 1 v 1] v 4",
    ),
    ("p1 ltr: 2 .. 2", "p1 ltr: 2 .4 2"),
    ("p1 ltr: 2 ... 2", "p1 ltr: 2 .6 2"),
    ("p1 ltr: 2 . 2", "p1 ltr: 2 .2 2"),
    ("p1 ltr: ~~", "p1 ltr: ~4"),
    ("p1 ltr: ~", "p1 ltr: ~2"),
    ("p1 ltr: ~~~", "p1 ltr: ~6"),
    ("p1 ltr: a:~~", "p1 ltr: a:~4"),
    ("p1 ltr: 2 ↝ 2", "p1 ltr: 2 ! 2"),
    ("p1 ltr: 2 ↝↑ 2 ↝↓3 2", "p1 ltr: 2 !^ 2 !v3 2"),
    ("p1 ltr: (1)×2↘2", "p1 ltr: (1)x2v2"),
    ("p1 ltr: (1)×2↗", "p1 ltr: (1)x2^"),
    ("p1 ltr: 1 ^1 1", "p1 ltr: 1 ^ 1"),
    ("p1 ltr: (1)x3^1", "p1 ltr: (1)x3^"),
    ("p1 ltr: (1)x3v1", "p1 ltr: (1)x3v"),
    ("p1 ltr: 1 !v1 1", "p1 ltr: 1 !v 1"),
    ("p1 ltr: ⑳[1] ②+1[1]", "p1 ltr: #20[1] #2+1[1]"),
    ("p1 ltr: →2{• ↑ •}", "p1 ltr: >2{* ^ *}"),
    # A lyric is told from a move by its colon, and is never rewritten.
    ("p1 ltr: v:2 v2 1", "p1 ltr: v:2 v2 1"),
    ("p1 ltr: x:1 1", "p1 ltr: x:1 1"),
    ("p1 ltr: ①[a:2 ↑ 1] ↓ 2 [...]①", "p1 ltr: #1[a:2 ^ 1] v 2 #1[2 ^ 1]"),
    ("p1 ltr: #1[a:2 ^ 1] v 2 [...]#1", "p1 ltr: #1[a:2 ^ 1] v 2 #1[2 ^ 1]"),
    (
        "p1 ltr: ①[a:2 ↑ 1]\np2 ltr: ↓ [...]①",
        "p1 ltr: #1[a:2 ^ 1]\np2 ltr: v #1[2 ^ 1]",
    ),
    (
        "p1 ltr: ①[(1)×2↗ >1{i:•} 2]\np2 ltr: = [...]①",
        "p1 ltr: #1[(1)x2^ >1{i:*} 2]\np2 ltr: = #1[(1)x2^ >1{*} 2]",
    ),
]


@pytest.mark.parametrize("given, expected", ALIASES)
def test_hazzat_signs_normalise_to_canonical_text(given, expected):
    assert write_hymn(parse_hymn(given)) == expected


def test_write_hymn_joins_with_newlines_and_no_trailing_one():
    text = "p1 ltr: 1\np2 ltr: v 2"
    assert write_hymn(parse_hymn(text)) == text


REJECTS = [
    "p1 ltr: 1 ?",
    "p1 ltr: 1\t1",
    "p1 ltr: x3",
    "p1 ltr: 1 ^2x",
    "p1 ltr: 1^ 1",
    "ltr: 1",
    "p1 sideways: 1",
    "p1 ltr:",
    "p1 ltr: ^",
    "p1 ltr: =",
    # a length, size, count or label below 1
    "p1 ltr: 0",
    "p1 ltr: ~0",
    "p1 ltr: .0",
    "p1 ltr: 1 ^0 1",
    "p1 ltr: 1 !v0 1",
    "p1 ltr: >0{*}",
    "p1 ltr: (1)x0",
    "p1 ltr: (1)x3^0",
    "p1 ltr: #0[1]",
    # a shift of 0
    "p1 ltr: #1+0[1]",
    "p1 ltr: #1-0[1]",
    "p1 ltr: #1+[1]",
    # a run of dots or tildes with a digit is not an alias
    "p1 ltr: ..2",
    "p1 ltr: ~~2",
    # a bare ! takes no size
    "p1 ltr: 1 !2 1",
    # unbalanced or unclosed brackets
    "p1 ltr: (1",
    "p1 ltr: 1)",
    "p1 ltr: #1[1",
    "p1 ltr: 1]",
    "p1 ltr: >1{*",
    "p1 ltr: 1}",
    "p1 ltr: (1]x2",
    "p1 ltr: (1)",
    "p1 ltr: (1)x",
    "p1 ltr: #1 [1]",
    "p1 ltr: #1",
    "p1 ltr: [1]",
    "p1 ltr: [..]#1",
    # empty brackets
    "p1 ltr: ()x2",
    "p1 ltr: #1[]",
    "p1 ltr: >1{}",
    # = only as the join
    "p1 ltr: 1 = 1",
    "p1 ltr: = =",
    "p1 ltr: = = 1",
    "p1 ltr: (= 1)x2",
    "p1 ltr: >1{= *}",
    # * only inside a fast group
    "p1 ltr: *",
    "p1 ltr: 1 • 1",
    "p1 ltr: a:*",
    # only * and moves inside a fast group
    "p1 ltr: >1{1}",
    "p1 ltr: >1{.2}",
    "p1 ltr: >1{(1)x2}",
    "p1 ltr: >1{#1[1]}",
    "p1 ltr: >1{>1{*}}",
    "p1 ltr: >1{a:2}",
    # a fast group is bead (move? bead)*
    "p1 ltr: >1{^ *}",
    "p1 ltr: >1{* ^}",
    "p1 ltr: >1{* ^ ^ *}",
    "p1 ltr: >1{^}",
    "p1 ltr: >{*}",
    # lyrics
    "p1 ltr: é:2",
    "p1 ltr: a1:2",
    "p1 ltr: a-b:2",
    "p1 ltr: <+>a:2",
    "p1 ltr: <+a:2",
    "p1 ltr: <+1>:2",
    "p1 ltr: (é):2",
    "p1 ltr: (a1):2",
    "p1 ltr: a:",
    "p1 ltr: a:^",
    "p1 ltr: a: 2",
    # a copy needs an earlier occurrence, and has no shifted form
    "p1 ltr: [...]#1",
    "p1 ltr: [...]①",
    "p1 ltr: #2[1] [...]#1",
    "p1 ltr: #1[1] [...]#1+1",
    "p1 ltr: [...]",
    # nesting and size limits end in NotationError, not a crash
    "p1 ltr: " + "(" * 5000,
    "p1 ltr: " + "#1[" * 5000,
    "p1 ltr: " + "1" * 5000,
    # a phrase that expands to more than 10,000 notes and pauses
    "p1 ltr: (1)x10001",
    "p1 ltr: (((1)x100)x100)x2",
    "p1 ltr: " + "(" * 9 + "1" + ")x10" * 9,
    "p1 ltr: #1[(1)x6000] [...]#1",
    # a motif with no notes or pauses has nothing to copy
    "p1 ltr: #1[^] [...]#1",
    "p1 ltr: #1[(^)x2] [...]#1",
    # a phrase id is letters, digits, _ and -
    "p.1 ltr: 1",
    "a:b ltr: 1",
    "p1é ltr: 1",
    "p 1 ltr: 1",
]


@pytest.mark.parametrize("text", REJECTS)
def test_the_parser_rejects(text):
    with pytest.raises(NotationError):
        parse_line(text)


@pytest.mark.parametrize("text", ["", "\n", "p1 ltr: 1\n\np2 ltr: 1", "\np1 ltr: 1", "p1 ltr: 1\n\n"])
def test_parse_hymn_rejects_blank_lines_and_empty_text(text):
    with pytest.raises(NotationError):
        parse_hymn(text)


def test_parse_line_rejects_a_newline():
    with pytest.raises(NotationError):
        parse_line("p1 ltr: 1\np2 ltr: 1")


def test_errors_name_the_problem_and_where():
    with pytest.raises(NotationError, match=r"line 2.*column 11"):
        parse_hymn("p1 ltr: 1\np2 ltr: 1 ?")
    assert issubclass(NotationError, ValueError)


def test_lyric_marks_are_read_into_letters():
    added = parse_line("p1 ltr: ⲧ<+ⲉ>ⲛ:2").items[0]
    assert added.lyric == Syllable((Letters("ⲧ", "plain"), Letters("ⲉ", "added"), Letters("ⲛ", "plain")))
    silent = parse_line("p1 ltr: <-ϩ>ⲁ:2").items[0]
    assert silent.lyric == Syllable((Letters("ϩ", "silent"), Letters("ⲁ", "plain")))


def test_jinkim_and_both_coptic_blocks_are_letters():
    jinkim = "ⲛ̀"  # ⲛ with a combining grave
    assert parse_line(f"p1 ltr: {jinkim}:2").items[0].lyric == syl(jinkim)
    both = "ϣⲁ"  # ϣ (Greek and Coptic block), ⲁ (Coptic block)
    assert parse_line(f"p1 ltr: {both}:2").items[0].lyric == syl(both)
    assert write_line(parse_line(f"p1 ltr: {jinkim}:2 (ⲁ):1")) == f"p1 ltr: {jinkim}:2 (ⲁ):1"


def doubling_line(depth, first="1"):
    """#1 is one note, and each later motif is two copies of the one before: 2**(depth-1) notes."""
    motifs = [f"#{k}[[...]#{k - 1} [...]#{k - 1}]" for k in range(2, depth + 1)]
    return "p1 ltr: " + " ".join([f"#1[{first}]", *motifs])


def parse_in_a_subprocess(text):
    """The outcome of parse_hymn, run apart so a hang fails the test instead of the suite."""
    code = (
        "import sys\n"
        "from hymnstring.notation import NotationError, parse_hymn\n"
        "try:\n"
        "    hymn = parse_hymn(sys.argv[1])\n"
        "except NotationError:\n"
        "    print('NotationError')\n"
        "else:\n"
        "    print('parsed', len(hymn.phrases))\n"
    )
    done = subprocess.run(
        [sys.executable, "-c", code, text],
        capture_output=True,
        text=True,
        timeout=20,
        cwd=SPEC.parents[2],
    )
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def test_motifs_that_copy_motifs_end_in_notation_error_quickly():
    assert parse_in_a_subprocess(doubling_line(40)) == "NotationError"


def test_copies_of_a_motif_with_no_notes_are_rejected_at_once():
    with pytest.raises(NotationError):
        parse_hymn(doubling_line(40, first="^"))


def test_motifs_that_copy_motifs_still_parse_within_the_cap():
    assert parse_in_a_subprocess(doubling_line(10)) == "parsed 1"


FRAGMENTS = [
    "1", "2", "~2", ".2", "^", "v2", "!", "!v", "(1)x2", "(1 ^ 1)x3^", "#1[1]", "#1[2 ^ 1]",
    ">2{* ^ *}", "ⲁ:2", "(ⲁ):2", "[...]#1", "#1+1[1]", "=", "(1)x2v",
]
NOISE = list("12^v!=.~*(){}[]#+-x:<>a ①↑↝→•×↗") + ["[...]", "#1[", ")x2", ">1{", "lou:", "\n"]


def test_arbitrary_input_never_raises_anything_but_notation_error():
    rng = random.Random(7)
    parsed = 0
    for _ in range(3000):
        if rng.random() < 0.8:  # mostly valid fragments, joined by spaces, with some noise
            parts = [rng.choice(FRAGMENTS if rng.random() < 0.9 else NOISE) for _ in range(rng.randint(1, 8))]
            body = " ".join(parts)
        else:
            body = "".join(rng.choice(NOISE) for _ in range(rng.randint(1, 14)))
        try:
            hymn = parse_hymn("p1 ltr: " + body)
        except NotationError:
            continue
        parsed += 1
        assert parse_hymn(write_hymn(hymn)) == hymn
        validate(hymn)
    assert parsed >= 500
