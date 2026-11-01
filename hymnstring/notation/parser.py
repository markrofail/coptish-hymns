"""Reads the text form into the model. Hazzat signs are read as aliases, token by token."""

import re
import unicodedata

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

MAX_DEPTH = 50  # brackets nested deeper than this are an error, not a stack overflow
MAX_DIGITS = 9
MAX_EVENTS = 10_000  # notes and pauses a phrase may expand to, so a repeat cannot fill memory

MOVE_UP = "^↑"
MOVE_DOWN = "v↓"
REPEAT_UP = "^↗"
REPEAT_DOWN = "v↘"
ABRUPT = "!↝"
FAST = ">→"
STAR = "*•"
TIMES = "x×"
CLOSERS = ")]}"
CIRCLED = {chr(0x2460 + n): n + 1 for n in range(20)}  # ① to ⑳

HEADER = re.compile(r"([A-Za-z0-9_-]+) (ltr|rtl):(?: |$)")


class NotationError(ValueError):
    """The text is not valid string notation. The message says what and where."""


def parse_line(line: str) -> Phrase:
    """One phrase alone. A `[...]` copy resolves only against this line."""
    return _parse_phrase(line, {}, {})


def parse_hymn(text: str) -> Hymn:
    """One phrase per line. A `[...]` copy resolves against the lines before it."""
    lines = text.split("\n")
    if lines and lines[-1] == "" and len(lines) > 1:
        lines.pop()  # one final newline ends the last line
    seen: dict[int, Motif] = {}
    known: dict[int, int] = {}
    phrases = []
    for number, line in enumerate(lines, start=1):
        try:
            phrases.append(_parse_phrase(line, seen, known))
        except NotationError as error:
            raise NotationError(f"line {number}: {error}") from None
    return Hymn(tuple(phrases))


def _parse_phrase(line: str, seen: dict[int, Motif], known: dict[int, int]) -> Phrase:
    parser = _Parser(line, seen, known)
    return parser.phrase()


def _is_letter(char: str) -> bool:
    return unicodedata.category(char)[0] in "LM"


def _events(items: tuple[Item, ...], known: dict[int, int]) -> int:
    """Notes and pauses once repeats are expanded, counted without expanding them.

    Stops as soon as the total passes the cap, and takes a registered motif's count from
    `known` (keyed by id), so a motif that copies motifs is not walked copy by copy."""
    total = 0
    for item in items:
        match item:
            case Note() | Pause():
                total += 1
            case Fast():
                total += sum(isinstance(i, Bead) for i in item.items)
            case Repeat():
                total += item.count * _events(item.items, known)
            case Motif():
                total += known[id(item)] if id(item) in known else _events(item.items, known)
        if total > MAX_EVENTS:
            break
    return total


def _strip(items: tuple[Item, ...], known: dict[int, int]) -> tuple[Item, ...]:
    """The same shape with every lyric removed. A registered motif has none, so it is reused."""
    return tuple(_strip_one(item, known) for item in items)


def _strip_one(item: Item | Bead, known: dict[int, int]) -> Item | Bead:
    match item:
        case Note():
            return Note(item.length, item.vibrato)
        case Bead():
            return Bead()
        case Fast():
            return Fast(item.length, tuple(_strip_one(i, known) for i in item.items))
        case Repeat():
            return Repeat(_strip(item.items, known), item.count, item.step)
        case Motif():
            return item if id(item) in known else Motif(item.label, item.shift, _strip(item.items, known))
    return item


class _Parser:
    def __init__(self, text: str, seen: dict[int, Motif], known: dict[int, int]):
        self.text = text
        self.pos = 0
        self.seen = seen  # first occurrence of each motif label, lyrics removed
        self.known = known  # id of each such motif to its event count; seen keeps them alive
        self.depth = 0

    # -- helpers

    def fail(self, message: str, at: int | None = None) -> NotationError:
        column = (self.pos if at is None else at) + 1
        return NotationError(f"{message} at column {column} in {self.text!r}")

    def peek(self) -> str:
        return self.text[self.pos : self.pos + 1]

    def at(self, chars: str) -> bool:
        return self.peek() != "" and self.peek() in chars

    def at_digit(self) -> bool:
        return self.at("0123456789")

    def skip_spaces(self) -> None:
        while self.peek() == " ":
            self.pos += 1

    def digits(self) -> str:
        start = self.pos
        while self.at_digit():
            self.pos += 1
        if self.pos - start > MAX_DIGITS:
            raise self.fail("number too long", start)
        return self.text[start : self.pos]

    def number(self, what: str) -> int:
        """A whole number of at least 1."""
        start = self.pos
        found = self.digits()
        if not found:
            raise self.fail(f"expected a number for the {what}")
        if int(found) < 1:
            raise self.fail(f"the {what} must be at least 1", start)
        return int(found)

    def label(self) -> int:
        if self.peek() == "#":
            self.pos += 1
            return self.number("motif label")
        if self.peek() in CIRCLED:
            self.pos += 1
            return CIRCLED[self.text[self.pos - 1]]
        raise self.fail("expected a motif label")

    def expect(self, char: str, what: str) -> None:
        if self.peek() != char:
            raise self.fail(f"expected {what}")
        self.pos += 1

    # -- lines

    def phrase(self) -> Phrase:
        header = HEADER.match(self.text)
        if not header:
            raise self.fail("expected a phrase id, ltr or rtl, and a colon")
        self.pos = header.end()
        self.skip_spaces()
        join = None
        if self.peek() == "=":
            join = SameLevel()
            self.pos += 1
            self.after_item(None)
        items = self.items(None)
        if join is None and items and isinstance(items[0], Move):
            join, items = items[0], items[1:]
        if not items:
            raise self.fail("a phrase needs at least one item after its join")
        if _events(items, self.known) > MAX_EVENTS:
            raise self.fail(f"a phrase can expand to at most {MAX_EVENTS} notes and pauses", 0)
        return Phrase(header.group(1), header.group(2), join, items)

    def after_item(self, closer: str | None) -> None:
        """Items are separated by spaces, and a closing bracket needs none."""
        if self.peek() == " ":
            self.skip_spaces()
        elif self.peek() and self.peek() != closer:
            raise self.fail("expected a space or the end of the bracket")

    def items(self, closer: str | None) -> tuple[Item, ...]:
        """Items up to the closer, which is left unread. None means the end of the line."""
        found = []
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise self.fail("brackets nested too deeply")
        self.skip_spaces()
        while True:
            char = self.peek()
            if char == "":
                if closer:
                    raise self.fail(f"unclosed bracket, expected {closer!r}")
                break
            if char == closer:
                break
            if char in CLOSERS:
                raise self.fail(f"unbalanced {char!r}")
            found.append(self.item())
            self.after_item(closer)
        self.depth -= 1
        return tuple(found)

    # -- items

    def item(self) -> Item:
        char = self.peek()
        if char == "[":
            return self.copy()
        if char == "#" or char in CIRCLED:
            return self.motif()
        if char == "(":
            return self.vowel_note() or self.repeat()
        if char in FAST:
            return self.fast()
        if char == ".":
            return self.pause()
        if char == "=":
            raise self.fail("'=' is only allowed as a phrase's join")
        if char in STAR:
            raise self.fail("'*' is only allowed inside a fast group")
        lyric = self.lyric()
        if lyric:
            return self.note(lyric)
        if char in ABRUPT + MOVE_UP + MOVE_DOWN:
            return self.move()
        if char == "~" or self.at_digit():
            return self.note(None)
        raise self.fail("unknown token")

    def lyric(self) -> Syllable | None:
        """A syllable and its colon, or nothing (and nothing consumed) if there is no colon."""
        start = self.pos
        parts: list[Letters] = []
        plain = ""
        while True:
            char = self.peek()
            if char and _is_letter(char):
                plain += char
                self.pos += 1
            elif self.text.startswith(("<+", "<-"), self.pos):
                end = self.text.find(">", self.pos)
                inner = self.text[self.pos + 2 : end] if end > 0 else ""
                if not inner or not all(_is_letter(c) for c in inner):
                    break
                if plain:
                    parts.append(Letters(plain, "plain"))
                    plain = ""
                parts.append(Letters(inner, "added" if self.text[self.pos + 1] == "+" else "silent"))
                self.pos = end + 1
            else:
                break
        if plain:
            parts.append(Letters(plain, "plain"))
        if not parts or self.peek() != ":":
            self.pos = start
            return None
        self.pos += 1
        if self.not_nfc("".join(p.text for p in parts)):
            raise self.fail("a lyric must be NFC-normalised", start)
        return Syllable(tuple(parts))

    @staticmethod
    def not_nfc(text: str) -> bool:
        return unicodedata.normalize("NFC", text) != text

    def vowel_note(self) -> Note | None:
        """`(letters):` before a note, or nothing if the bracket is a repeat."""
        start = self.pos
        end = start + 1
        while end < len(self.text) and _is_letter(self.text[end]):
            end += 1
        if end == start + 1 or not self.text.startswith("):", end):
            return None
        letters = self.text[start + 1 : end]
        if self.not_nfc(letters):
            raise self.fail("a lyric must be NFC-normalised", start)
        self.pos = end + 2
        return self.note(Vowel(letters))

    def note(self, lyric: Syllable | Vowel | None) -> Note:
        tildes = 0
        while self.peek() == "~":
            tildes += 1
            self.pos += 1
        start = self.pos
        found = self.digits()
        if tildes > 1 and found:
            raise self.fail("a run of tildes cannot be followed by a length", start)
        if not found and not tildes:
            raise self.fail("expected a note length")
        length = int(found) if found else 2 * tildes
        if length < 1:
            raise self.fail("a length must be at least 1", start)
        return Note(length, tildes > 0, lyric)

    def pause(self) -> Pause:
        dots = 0
        while self.peek() == ".":
            dots += 1
            self.pos += 1
        start = self.pos
        found = self.digits()
        if dots > 1 and found:
            raise self.fail("a run of dots cannot be followed by a length", start)
        length = int(found) if found else 2 * dots
        if length < 1:
            raise self.fail("a length must be at least 1", start)
        return Pause(length)

    def move(self) -> Move:
        abrupt = self.at(ABRUPT)
        if abrupt:
            self.pos += 1
        char = self.peek()
        if self.at(MOVE_UP + MOVE_DOWN):
            self.pos += 1
            size = self.number("move size") if self.at_digit() else 1
            return Move(abrupt, size if char in MOVE_UP else -size)
        if self.at_digit():
            raise self.fail("a bare '!' takes no size")
        return Move(True, 0)

    def fast(self) -> Fast:
        self.pos += 1
        length = self.number("fast group length")
        self.expect("{", "'{' after the fast group length")
        found: list[Bead | Move] = []
        self.skip_spaces()
        while self.peek() != "}":
            char = self.peek()
            if char == "":
                raise self.fail("unclosed bracket, expected '}'")
            if char in STAR:
                self.pos += 1
                found.append(Bead())
            elif char == "(" and (bead := self.vowel_bead()):
                found.append(bead)
            elif (lyric := self.lyric()) is not None:
                if not self.at(STAR):
                    raise self.fail("a lyric in a fast group must be followed by '*'")
                self.pos += 1
                found.append(Bead(lyric))
            elif char in ABRUPT + MOVE_UP + MOVE_DOWN:
                found.append(self.move())
            else:
                raise self.fail("only '*' and moves are allowed inside a fast group")
            self.after_item("}")
        self.pos += 1
        if not any(isinstance(i, Bead) for i in found):
            raise self.fail("a fast group needs at least one '*'")
        # beads with at most one move between neighbours, and none at either end
        if isinstance(found[0], Move) or isinstance(found[-1], Move):
            raise self.fail("a fast group must start and end with a '*'")
        if any(isinstance(a, Move) and isinstance(b, Move) for a, b in zip(found, found[1:])):
            raise self.fail("a fast group allows at most one move between two notes")
        return Fast(length, tuple(found))

    def vowel_bead(self) -> Bead | None:
        note_start = self.pos
        end = note_start + 1
        while end < len(self.text) and _is_letter(self.text[end]):
            end += 1
        if end == note_start + 1 or not self.text.startswith("):", end):
            return None
        letters = self.text[note_start + 1 : end]
        if self.not_nfc(letters):
            raise self.fail("a lyric must be NFC-normalised", note_start)
        self.pos = end + 2
        if not self.at(STAR):
            raise self.fail("a lyric in a fast group must be followed by '*'")
        self.pos += 1
        return Bead(Vowel(letters))

    def repeat(self) -> Repeat:
        open_at = self.pos
        self.pos += 1
        body = self.items(")")
        if not body:
            raise self.fail("a repeat needs at least one item", open_at)
        self.pos += 1
        if not self.at(TIMES):
            raise self.fail("a repeat bracket must be followed by 'x' and a count")
        self.pos += 1
        count = self.number("repeat count")
        step = 0
        char = self.peek()
        if self.at(REPEAT_UP + REPEAT_DOWN):
            self.pos += 1
            size = self.number("repeat level step") if self.at_digit() else 1
            step = size if char in REPEAT_UP else -size
        return Repeat(body, count, step)

    def motif(self) -> Motif:
        label = self.label()
        shift = 0
        if self.at("+-"):
            sign = 1 if self.peek() == "+" else -1
            self.pos += 1
            shift = sign * self.number("motif shift")
        open_at = self.pos
        self.expect("[", "'[' after the motif label")
        body = self.items("]")
        if not body:
            raise self.fail("a motif needs at least one item", open_at)
        self.pos += 1
        events = _events(body, self.known)
        if events > MAX_EVENTS:
            raise self.fail(f"a motif can expand to at most {MAX_EVENTS} notes and pauses", open_at)
        if label not in self.seen:
            first = Motif(label, 0, _strip(body, self.known))
            self.seen[label] = first
            self.known[id(first)] = events
        return Motif(label, shift, body)

    def copy(self) -> Motif:
        if not self.text.startswith("[...]", self.pos):
            raise self.fail("a motif bracket needs its label before it, as in #1[...]")
        self.pos += 5
        start = self.pos
        label = self.label()
        if label not in self.seen:
            raise self.fail(f"no earlier occurrence of motif {label} to copy", start)
        return self.seen[label]
