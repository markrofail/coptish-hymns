"""Expands items into flat events with levels, the way the synthesiser and checks read them."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from hymnstring.notation.model import (
    Bead,
    Fast,
    Hymn,
    Item,
    Motif,
    Move,
    Note,
    Pause,
    Phrase,
    Repeat,
    Syllable,
    Vowel,
)


@dataclass(frozen=True)
class FlatNote:
    level: int
    length: Fraction
    kind: Literal["note", "vibrato", "fast"]
    lyric: Syllable | Vowel | None
    move: Move | None  # the move into this note, including a repeat's join


@dataclass(frozen=True)
class FlatPause:
    level: int
    length: Fraction


FlatEvent = FlatNote | FlatPause


@dataclass(frozen=True)
class MotifUse:
    """One occurrence of a motif. The shape leaves out lyrics, levels and the first move."""

    label: int
    shift: int
    start_level: int
    shape: tuple[tuple[Move | None, str, Fraction], ...]  # (move, kind, length) per event
    first_event: int  # index into Flat.events
    end_event: int  # exclusive


@dataclass(frozen=True)
class RepeatUse:
    """One repeat, spanning all its copies."""

    count: int
    step: int
    first_event: int
    end_event: int  # exclusive


@dataclass(frozen=True)
class Flat:
    events: tuple[FlatEvent, ...]
    end_level: int
    motifs: tuple[MotifUse, ...]
    repeats: tuple[RepeatUse, ...]  # outer before inner, like motifs


@dataclass(frozen=True)
class ChainedPhrase:
    """A phrase flattened at its place in its chain: level 0 is where the chain starts."""

    index: int  # the phrase's position in the hymn
    phrase: Phrase
    chain: int  # counts from 0
    flat: Flat


def flatten(items: tuple[Item, ...], start_level: int = 0) -> Flat:
    walk = _Walk(start_level)
    walk.items(items, lyrics=True)
    return Flat(tuple(walk.events), walk.level, tuple(walk.motifs), tuple(walk.repeats))


def walk_chains(
    hymn: Hymn, items_of: Callable[[Phrase], tuple[Item, ...]] = lambda phrase: phrase.items
) -> Iterator[ChainedPhrase]:
    """Each phrase in order, flattened on the level its join leads to. The first phrase, or one with
    no join, starts a new chain at level 0. A move join adds its change to where the last phrase
    ended, which after a trailing pause is the level the pause held. `=` adds nothing."""
    chain, end_level = -1, 0
    for index, phrase in enumerate(hymn.phrases):
        if index == 0 or phrase.join is None:
            chain += 1  # no join, so no shared level: a new chain with its own level 0
            start = 0
        else:
            start = end_level + (phrase.join.change if isinstance(phrase.join, Move) else 0)
        flat = flatten(items_of(phrase), start)
        end_level = flat.end_level
        yield ChainedPhrase(index, phrase, chain, flat)


class _Walk:
    def __init__(self, level: int):
        self.level = level
        self.pending: Move | None = None  # the move waiting for the next note
        self.events: list[FlatEvent] = []
        self.motifs: list[MotifUse] = []
        self.repeats: list[RepeatUse] = []

    def items(self, items: tuple[Item, ...], lyrics: bool) -> None:
        for item in items:
            self.item(item, lyrics)

    def move(self, move: Move) -> None:
        self.level += move.change
        self.pending = move

    def note(self, length: Fraction, kind: str, lyric: Syllable | Vowel | None) -> None:
        self.events.append(FlatNote(self.level, length, kind, lyric, self.pending))
        self.pending = None

    def item(self, item: Item, lyrics: bool) -> None:
        match item:
            case Note():
                kind = "vibrato" if item.vibrato else "note"
                self.note(Fraction(item.length), kind, item.lyric if lyrics else None)
            case Pause():
                self.events.append(FlatPause(self.level, Fraction(item.length)))
            case Move():
                self.move(item)
            case Fast():
                beads = sum(isinstance(i, Bead) for i in item.items)
                for part in item.items:
                    if isinstance(part, Move):
                        self.move(part)
                    else:
                        self.note(Fraction(item.length, beads), "fast", part.lyric if lyrics else None)
            case Repeat():
                self.repeat(item, lyrics)
            case Motif():
                self.motif(item, lyrics)

    def repeat(self, repeat: Repeat, lyrics: bool) -> None:
        slot = len(self.repeats)
        self.repeats.append(None)  # type: ignore[arg-type]  # filled below, so outer repeats come first
        first, start = len(self.events), self.level
        for copy in range(repeat.count):
            if copy:
                needed = start + copy * repeat.step - self.level
                self.level += needed
                self.pending = Move(False, needed) if needed else None
            self.items(repeat.items, lyrics and copy == 0)
        self.repeats[slot] = RepeatUse(repeat.count, repeat.step, first, len(self.events))

    def motif(self, motif: Motif, lyrics: bool) -> None:
        slot = len(self.motifs)
        self.motifs.append(None)  # type: ignore[arg-type]  # filled below, so outer motifs come first
        first, start = len(self.events), self.level
        self.items(motif.items, lyrics)
        self.motifs[slot] = MotifUse(
            motif.label, motif.shift, start, _shape(self.events[first:]), first, len(self.events)
        )


def _shape(events: list[FlatEvent]) -> tuple[tuple[Move | None, str, Fraction], ...]:
    shape = []
    for event in events:
        if isinstance(event, FlatNote):
            shape.append((event.move, event.kind, event.length))
        else:
            shape.append((None, "pause", event.length))
    if shape:
        shape[0] = (None,) + shape[0][1:]
    return tuple(shape)
