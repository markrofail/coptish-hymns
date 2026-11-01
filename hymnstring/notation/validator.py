"""Checks a parsed hymn against SPEC.md's list of what makes a string invalid.

The parser already refuses unknown tokens, sizes below 1 and a misplaced `=`. What is left is
structure (where moves and pauses may sit) and motifs (shape, then level within a chain).
"""

from dataclasses import dataclass, replace

from hymnstring.notation.flatten import flatten
from hymnstring.notation.model import (
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
        if index == 0 and phrase.join is not None:
            found.append((index, Problem("first_join", phrase.phrase_id, "the first phrase of a hymn cannot have a join")))
        found += [(index, problem) for problem in validate_phrase(phrase)]
    found += _motifs(hymn)
    found.sort(key=lambda pair: pair[0])  # stable: structure before motifs within a phrase
    return [problem for _, problem in found]


def validate_phrase(phrase: Phrase) -> list[Problem]:
    """The problems a phrase has on its own: its structure, and a motif in a level-changing
    repeat. What needs the rest of the hymn is left out: a join on the first phrase, and how
    motifs compare with each other."""
    found = _structure(phrase)
    _, hits = _without_rising_motifs(phrase.items)
    found += [_rising_problem(phrase)] * hits
    return found


def _rising_problem(phrase: Phrase) -> Problem:
    return Problem("motif_level", phrase.phrase_id, "a motif cannot sit in a repeat that changes level")


# -- structure


def _structure(phrase: Phrase) -> list[Problem]:
    found: list[Problem] = []

    def add(rule: str, message: str) -> None:
        found.append(Problem(rule, phrase.phrase_id, message))

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
        items, _ = _without_rising_motifs(phrase.items)  # those are validate_phrase's problems
        flat = flatten(items, start)
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


def _without_rising_motifs(items: tuple[Item, ...], in_motif: bool = False) -> tuple[tuple[Item, ...], int]:
    """Items with the motif labels taken off any level-changing repeat's body, and how many
    such repeats held a motif. Each is one defect, whatever its count, and its copies would
    otherwise each be reported. A same-level repeat is cut to one copy for the same reason:
    its copies start on one level, so they repeat the first copy's motif problems. Inside a motif
    the copies stay, because they are part of the motif's shape."""
    kept: list[Item] = []
    hits = 0
    for item in items:
        if isinstance(item, Repeat) and item.step != 0:
            body = _unlabelled(item.items)
            hits += body != item.items
            item = replace(item, items=body)
        elif isinstance(item, Repeat | Motif):
            body, inner = _without_rising_motifs(item.items, in_motif or isinstance(item, Motif))
            hits += inner
            item = replace(item, items=body)
            if isinstance(item, Repeat) and not in_motif:
                item = replace(item, count=1)  # same-level copies all start on one level
        kept.append(item)
    return tuple(kept), hits


def _unlabelled(items: tuple[Item, ...]) -> tuple[Item, ...]:
    """The same items with every motif bracket removed."""
    kept: list[Item] = []
    for item in items:
        if isinstance(item, Motif):
            kept += _unlabelled(item.items)
        elif isinstance(item, Repeat):
            kept.append(replace(item, items=_unlabelled(item.items)))
        else:
            kept.append(item)
    return tuple(kept)
