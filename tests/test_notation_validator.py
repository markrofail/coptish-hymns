import pytest

from hymnstring.notation import parse_hymn
from hymnstring.notation.validator import validate

DEMO = (
    "p1 ltr: #1[A:2 ^ 1 v 1] ^ lē:~2 .2 v (lou:1)x3^ >1{i:*} a:2 !v2 "
    "#1[(a):2 ^ 1 v 1] v 4"
)

# (name, hymn text, expected [(rule, phrase_id)])
CASES = [
    ("demo is valid", DEMO, []),
    ("same motif twice", "p1 ltr: #1[2 ^ 1] v 2 #1[ⲡⲉ:2 ^ 1]", []),
    ("shifted motifs", "p1 ltr: #1[2 ^ 1] #1+1[2 ^ 1] v3 #1-1[2 ^ 1]", []),
    ("motif in a same-level repeat", "p1 ltr: (#1[1 ^ 1])x2", []),
    ("repeat expands to the same shape", "p1 ltr: #1[(1)x3 ^ 2] v #1[1 1 1 ^ 2]", []),
    ("bare abrupt move", "p1 ltr: 1 ! 1", []),
    ("shape differs", "p1 ltr: #1[2 ^ 1] v #1[2 ^ 2]", [("motif_shape", "p1")]),
    ("plain motif on another level", "p1 ltr: #1[2 ^ 1] #1[2 ^ 1]", [("motif_level", "p1")]),
    ("shifted motif off its shift", "p1 ltr: #1[2 ^ 1] v #1+1[2 ^ 1]", [("motif_level", "p1")]),
    ("motif in a rising repeat", "p1 ltr: (#1[1 ^ 1])x2^", [("motif_level", "p1")]),
    ("shifted before plain", "p1 ltr: #1+1[2] #1[2]", [("motif_order", "p1")]),
    (
        "other chain, shape only",
        "p1 ltr: #1[2 ^ 1]\np2 ltr: 2 #1[2 ^ 1]",
        [],
    ),
    (
        "same-level join, motif on another level",
        "p1 ltr: #1[2 ^ 1]\np2 ltr: = #1[2 ^ 1]",
        [("motif_level", "p2")],
    ),
    ("join down one", "p1 ltr: #1[2 ^ 1]\np2 ltr: v #1[2 ^ 1]", []),
    (
        "join down two",
        "p1 ltr: #1[2 ^ 1]\np2 ltr: v2 #1[2 ^ 1]",
        [("motif_level", "p2")],
    ),
    (
        "bare abrupt join",
        "p1 ltr: #1[2 ^ 1]\np2 ltr: ! #1[2 ^ 1]",
        [("motif_level", "p2")],
    ),
    (
        "a phrase with no join starts a new chain",
        "p1 ltr: #1[2 ^ 1]\np2 ltr: v 1\np3 ltr: 2\np4 ltr: 5 ^ 4 #1[2 ^ 1]",
        [],
    ),
    ("motif in a rising repeat of three", "p1 ltr: (#1[1 ^ 1])x3^", [("motif_level", "p1")]),
    ("motif deep in a rising repeat", "p1 ltr: ((#1[1])x2 ^ 1)x3^", [("motif_level", "p1")]),
    (
        "p4 chains from p3, which broke the chain",
        "p1 ltr: #1[2 ^ 1]\np2 ltr: v 1\np3 ltr: #1[2 ^ 1] ^ 1\np4 ltr: v2 #1[2 ^ 1]",
        [],
    ),
    (
        "p4 chains from p3, wrong join",
        "p1 ltr: #1[2 ^ 1]\np2 ltr: v 1\np3 ltr: #1[2 ^ 1] ^ 1\np4 ltr: v #1[2 ^ 1]",
        [("motif_level", "p4")],
    ),
    ("join on the first phrase", "p1 ltr: ^ 1", [("first_join", "p1")]),
    ("pause first", "p1 ltr: .2 1", [("phrase_start", "p1")]),
    ("ends on a move", "p1 ltr: 1 ^", [("phrase_end", "p1")]),
    ("pause after a same-level join", "p1 ltr: 1\np2 ltr: = .2 1", [("phrase_start", "p2")]),
    ("move after a join move", "p1 ltr: 1\np2 ltr: ^ ^ 1", [("phrase_start", "p2")]),
    ("two moves", "p1 ltr: 1 ^ ^ 1", [("move_follower", "p1")]),
    ("move then pause", "p1 ltr: 1 ^ .2 1", [("move_follower", "p1")]),
    ("corner then slope", "p1 ltr: 1 ! ^ 1", [("move_follower", "p1")]),
    ("count of one", "p1 ltr: (1)x1", [("repeat_count", "p1")]),
    ("repeat starts on a move", "p1 ltr: (^ 1)x2", [("bracket_edge", "p1")]),
    ("repeat ends on a move", "p1 ltr: (1 ^)x2", [("bracket_edge", "p1")]),
    ("repeat starts on a pause", "p1 ltr: (.2 1)x2", [("bracket_edge", "p1")]),
    ("motif starts on a move", "p1 ltr: #1[^ 1]", [("bracket_edge", "p1")]),
    ("motif ends on a move", "p1 ltr: #1[1 ^]", [("bracket_edge", "p1")]),
    ("move before a bracket that starts on a pause", "p1 ltr: 1 ^ (.2 1)x2", [("bracket_edge", "p1")]),
    ("problems come in phrase order", "p1 ltr: 1 ^\np2 ltr: 1 ^ ^ 1", [("phrase_end", "p1"), ("move_follower", "p2")]),
]


@pytest.mark.parametrize("text, expected", [case[1:] for case in CASES], ids=[case[0] for case in CASES])
def test_validate(text, expected):
    problems = validate(parse_hymn(text))

    assert [(problem.rule, problem.phrase_id) for problem in problems] == expected
