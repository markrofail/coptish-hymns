"""Checks a parsed hymn against SPEC.md's list of what makes a string invalid.

The parser already refuses unknown tokens, sizes below 1 and a misplaced `=`. What is left is
structure (where moves and pauses may sit) and motifs (shape, then level within a chain).
"""

from dataclasses import dataclass

from hymnstring.notation.flatten import flatten
from hymnstring.notation.model import (
    Fast,
    Hymn,
    Item,
    Motif,
    Move,
    Pause,
    Phrase,
    Repeat,
)


@dataclass(frozen=True)
class Problem:
    rule: str
    phrase_id: str
    message: str


def validate(hymn: Hymn) -> list[Problem]:
    """Problems in phrase order, one per defect. Empty when the hymn is valid."""
    found: list[tuple[int, Problem]] = []
    for index, phrase in enumerate(hymn.phrases):
        found += [(index, problem) for problem in _structure(phrase, index)]
    found += _motifs(hymn)
    found.sort(key=lambda pair: pair[0])  # stable: structure before motifs within a phrase
    return [problem for _, problem in found]


# -- structure


def _structure(phrase: Phrase, index: int) -> list[Problem]:
    found: list[Problem] = []

    def add(rule: str, message: str) -> None:
        found.append(Problem(rule, phrase.phrase_id, message))

    if index == 0 and phrase.join is not None:
        add("first_join", "the first phrase of a hymn cannot have a join")
    first, last = phrase.items[0], phrase.items[-1]
    if isinstance(first, Pause | Move):
        add("phrase_start", "a phrase must start on a note, after any join")
    if isinstance(last, Move):
        add("phrase_end", "a phrase cannot end on a move")
    _items(phrase.items, add)
    return found


def _items(items: tuple[Item, ...], add) -> None:
    """Moves followed by moves or pauses, and the brackets inside this list."""
    for here, after in zip(items, items[1:]):
        if isinstance(here, Move) and isinstance(after, Pause | Move):
            add("move_follower", "a move cannot be followed by another move or a pause")
    for item in items:
        match item:
            case Fast():
                _items(item.items, add)
            case Repeat():
                if item.count < 2:
                    add("repeat_count", "a repeat needs a count of at least 2")
                _edges(item.items, add)
                _items(item.items, add)
            case Motif():
                _edges(item.items, add)
                _items(item.items, add)


def _edges(body: tuple[Item, ...], add) -> None:
    starts_badly = isinstance(body[0], Pause | Move)
    if starts_badly:
        add("bracket_edge", "a bracket cannot start with a pause or a move")
    # a one-item body that fails at the start is one defect, not two
    if isinstance(body[-1], Move) and not (starts_badly and len(body) == 1):
        add("bracket_edge", "a bracket cannot end on a move")


# -- motifs


def _motifs(hymn: Hymn) -> list[tuple[int, Problem]]:
    found: list[tuple[int, Problem]] = []
    first_shape: dict[int, tuple] = {}  # per label, the shape of its first occurrence in the hymn
    plain_seen: set[int] = set()
    base: dict[tuple[int, int], int] = {}  # (chain, label) -> level of a plain occurrence
    chain, end_level = 0, 0
    for index, phrase in enumerate(hymn.phrases):
        if index == 0 or phrase.join is None:
            chain += 1  # no join, so no shared level: a new chain with its own level 0
            start = 0
        else:
            start = end_level + (phrase.join.change if isinstance(phrase.join, Move) else 0)
        flat = flatten(phrase.items, start)
        end_level = flat.end_level
        for use in flat.motifs:

            def add(rule: str, message: str) -> None:
                found.append((index, Problem(rule, phrase.phrase_id, f"#{use.label}: {message}")))

            if use.label not in first_shape:
                first_shape[use.label] = use.shape
            elif use.shape != first_shape[use.label]:
                add("motif_shape", "differs in shape from its first occurrence")
            if use.shift == 0:
                plain_seen.add(use.label)
            elif use.label not in plain_seen:
                add("motif_order", "a shifted motif cannot come before its first plain occurrence")
                continue
            # a plain occurrence is `start` levels up; a shifted one is that many from the plain
            wanted = base.setdefault((chain, use.label), use.start_level - use.shift)
            if use.start_level - use.shift != wanted:
                add("motif_level", "starts on a level that does not fit the others in its chain")
    return found
