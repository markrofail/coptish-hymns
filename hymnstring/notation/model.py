"""What a string is, once parsed. No levels live here: only what the text says."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Letters:
    text: str
    mark: Literal["plain", "added", "silent"]  # added is red, silent is gray


@dataclass(frozen=True)
class Syllable:
    parts: tuple[Letters, ...]


@dataclass(frozen=True)
class Vowel:
    letters: str


@dataclass(frozen=True)
class Note:
    length: int
    vibrato: bool = False
    lyric: Syllable | Vowel | None = None


@dataclass(frozen=True)
class Pause:
    length: int


@dataclass(frozen=True)
class Move:
    abrupt: bool
    change: int  # signed levels; only a bare ! is 0


@dataclass(frozen=True)
class SameLevel:
    """The `=` join."""


@dataclass(frozen=True)
class Bead:
    """A `*` in a fast group."""

    lyric: Syllable | Vowel | None = None


@dataclass(frozen=True)
class Fast:
    length: int
    items: tuple[Bead | Move, ...]


@dataclass(frozen=True)
class Repeat:
    items: tuple["Item", ...]  # one written copy
    count: int
    step: int = 0  # signed levels per copy


@dataclass(frozen=True)
class Motif:
    label: int
    shift: int
    items: tuple["Item", ...]


@dataclass(frozen=True)
class Phrase:
    phrase_id: str
    direction: Literal["ltr", "rtl"]
    join: Move | SameLevel | None
    items: tuple["Item", ...]


@dataclass(frozen=True)
class Hymn:
    phrases: tuple[Phrase, ...]


Item = Note | Fast | Pause | Move | Repeat | Motif
