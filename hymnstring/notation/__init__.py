"""String notation: the model, the parser and writer for its text form, `flatten`, and the validator."""

from hymnstring.notation.flatten import Flat, FlatEvent, FlatNote, FlatPause, MotifUse, flatten
from hymnstring.notation.model import (
    Bead,
    Fast,
    Hymn,
    Item,
    Letters,
    Motif,
    Move,
    Note,
    Pause,
    Phrase,
    Repeat,
    SameLevel,
    Syllable,
    Vowel,
)
from hymnstring.notation.parser import NotationError, parse_hymn, parse_line
from hymnstring.notation.validator import Problem, validate, validate_phrase
from hymnstring.notation.writer import write_hymn, write_line

__all__ = [
    "Bead",
    "Fast",
    "Flat",
    "FlatEvent",
    "FlatNote",
    "FlatPause",
    "Hymn",
    "Item",
    "Letters",
    "Motif",
    "MotifUse",
    "Move",
    "NotationError",
    "Note",
    "Pause",
    "Phrase",
    "Problem",
    "Repeat",
    "SameLevel",
    "Syllable",
    "Vowel",
    "flatten",
    "parse_hymn",
    "parse_line",
    "validate",
    "validate_phrase",
    "write_hymn",
    "write_line",
]
