"""Writes the canonical text: ASCII signs, sizes of 1 left out, one space between tokens."""

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
    SameLevel,
    Syllable,
    Vowel,
)
from hymnstring.notation.parser import NotationError


def write_hymn(hymn: Hymn) -> str:
    return "\n".join(write_line(phrase) for phrase in hymn.phrases)


def write_line(phrase: Phrase) -> str:
    tokens = [] if phrase.join is None else [_join(phrase.join)]
    tokens += [_item(item) for item in phrase.items]
    return f"{phrase.phrase_id} {phrase.direction}: " + " ".join(tokens)


def _join(join: Move | SameLevel) -> str:
    return "=" if isinstance(join, SameLevel) else _move(join)


def _size(size: int) -> str:
    return "" if size == 1 else str(size)


def _move(move: Move) -> str:
    sign = "!" if move.abrupt else ""
    if move.change == 0:
        if not move.abrupt:
            raise NotationError("a smooth move cannot have a change of 0")
        return sign
    return sign + ("^" if move.change > 0 else "v") + _size(abs(move.change))


def _lyric(lyric: Syllable | Vowel | None) -> str:
    if lyric is None:
        return ""
    if isinstance(lyric, Vowel):
        return f"({lyric.letters}):"
    marks = {"plain": "{}", "added": "<+{}>", "silent": "<-{}>"}
    return "".join(marks[part.mark].format(part.text) for part in lyric.parts) + ":"


def _item(item: Item | Bead) -> str:
    match item:
        case Note():
            return f"{_lyric(item.lyric)}{'~' if item.vibrato else ''}{item.length}"
        case Pause():
            return f".{item.length}"
        case Move():
            return _move(item)
        case Bead():
            return _lyric(item.lyric) + "*"
        case Fast():
            return f">{item.length}{{" + " ".join(_item(i) for i in item.items) + "}"
        case Repeat():
            step = "" if item.step == 0 else ("^" if item.step > 0 else "v") + _size(abs(item.step))
            return "(" + " ".join(_item(i) for i in item.items) + f")x{item.count}{step}"
        case Motif():
            shift = f"{item.shift:+d}" if item.shift else ""
            return f"#{item.label}{shift}[" + " ".join(_item(i) for i in item.items) + "]"
    raise NotationError(f"cannot write {item!r}")
