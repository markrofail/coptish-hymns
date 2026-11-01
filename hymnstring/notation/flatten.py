"""Expands items into flat events with levels, the way the synthesiser and checks read them."""

from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from hymnstring.notation.model import (
    Bead,
    Fast,
    Item,
    Motif,
    Move,
    Note,
    Pause,
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


@dataclass(frozen=True)
class Flat:
    events: tuple[FlatEvent, ...]
    end_level: int
    motifs: tuple[MotifUse, ...]


def flatten(items: tuple[Item, ...], start_level: int = 0) -> Flat:
    walk = _Walk(start_level)
    walk.items(items, lyrics=True)
    return Flat(tuple(walk.events), walk.level, tuple(walk.motifs))


class _Walk:
    def __init__(self, level: int):
        self.level = level
        self.pending: Move | None = None  # the move waiting for the next note
        self.events: list[FlatEvent] = []
        self.motifs: list[MotifUse] = []

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
        start = self.level
        for copy in range(repeat.count):
            if copy:
                needed = start + copy * repeat.step - self.level
                self.level += needed
                self.pending = Move(False, needed) if needed else None
            self.items(repeat.items, lyrics and copy == 0)

    def motif(self, motif: Motif, lyrics: bool) -> None:
        slot = len(self.motifs)
        self.motifs.append(None)  # type: ignore[arg-type]  # filled below, so outer motifs come first
        first, start = len(self.events), self.level
        self.items(motif.items, lyrics)
        self.motifs[slot] = MotifUse(motif.label, motif.shift, start, _shape(self.events[first:]))


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
