"""Random strings, each written together with its own plan of what it means.

A hymn is built from small recipes, and walking a recipe writes its text and plans its events in one
pass. The plan's levels, repeat copies, joins, syllables, causes and chain offsets are worked out here
with plain arithmetic, never with `flatten`, `walk_chains` or the score, so checking the synthesiser's
true values against it compares two independent derivations of one string. Rule numbers are those in
docs/superpowers/plans/2026-11-02-synthesiser.md.

Some vibrato notes are shorter than two cycles of the drawn vibrato rate, so a vibrato detector scored
on these hymns should allow for spans too short to measure a rate.
"""

import random
from dataclasses import dataclass
from fractions import Fraction
from typing import Literal

from hymnstring.contracts import HymnString, SynthSettings
from hymnstring.contracts.judgement import PhraseString
from hymnstring.contracts.synth import SynthSection

LOW, HIGH = -5, 5  # every note's hymn level stays between these, so a hymn spans at most 10 levels
SYLLABLES = ("ⲁ", "ⲉ", "ⲟⲩ", "ⲡⲓ", "ⲛⲉⲙ", "ϩⲁ", "ϣⲁ", "ⲙⲁⲣ", "ⲧ<+ⲉ>ⲛ", "ⲫ<+ⲉ>ⲓ", "<-ϩ>ⲁ", "ⲁⲙ<-ϩ>")
VOWELS = ("ⲁ", "ⲉ", "ⲟ")


@dataclass(frozen=True)
class PlannedEvent:
    phrase: int  # counting from 0
    kind: Literal["note", "vibrato", "fast", "pause"]
    length: Fraction  # in half-note units
    level: int  # in the hymn, not in its phrase; 0 for a pause
    syllable: int | None
    cause: str | None
    slides_in: bool  # a smooth, non-zero move reaches this note straight from a note before it


@dataclass(frozen=True)
class RandomHymn:
    string: HymnString
    events: tuple[PlannedEvent, ...]


def random_hymn(seed: int) -> RandomHymn:
    """A valid, canonical string and the events it should sing. `HymnString` is the first check."""
    writer = _Writer(random.Random(seed))
    phrases = tuple(writer.phrase(index) for index in range(writer.rng.randint(1, 4)))
    return RandomHymn(HymnString(format_version=1, phrases=phrases), tuple(writer.events))


def random_settings(seed: int, phrases: int) -> SynthSettings:
    """Settings for a hymn of this many phrases. Tempo and step change at random phrase boundaries."""
    rng = random.Random(seed + 1_000_000)
    firsts = [0] + sorted(rng.sample(range(1, phrases), rng.randint(1, min(3, phrases)) - 1))
    return SynthSettings(
        seed=seed,
        sections=tuple(
            SynthSection(
                first_phrase=first, half_note_s=rng.uniform(0.15, 0.5), step_cents=rng.uniform(80, 240)
            )
            for first in firsts
        ),
        base_hz=rng.uniform(100, 180),
        vibrato_rate_hz=rng.uniform(4.5, 6.5),
        vibrato_width_cents=rng.uniform(60, 140),
        hop_s=rng.choice((0.005, 0.01, 0.02)),
        slope_s=rng.choice((0.04, 0.08, 0.12)),
    )


# -- recipes: plain tuples, so that one can be walked again for each copy of a repeat or use of a motif
#   ("note", length, vibrato)  ("pause", length)  ("move", abrupt, change)
#   ("fast", length, gaps)     gaps[i] is the move before bead i, or None
#   ("repeat", body, count, step)    ("motif", label, shift, body)    a body is a tuple of recipes


def _arrow(change: int) -> str:
    """^ or v and its size, with a size of 1 left out; nothing for no change."""
    size = abs(change)
    return "" if change == 0 else ("^" if change > 0 else "v") + (str(size) if size > 1 else "")


def _move(rng: random.Random) -> tuple[bool, int]:
    """A random move inside a body: abrupt or not, and how far. Now and then a bare tick."""
    if rng.random() < 0.1:
        return True, 0
    return rng.random() < 0.3, rng.choice((-2, -1, -1, 1, 1, 2))


def _leaf(rng: random.Random, pause_ok: bool) -> tuple:
    kind = rng.choices(("note", "vibrato", "fast", "pause"), (6, 2, 3, 2 * pause_ok))[0]
    if kind == "pause":
        return "pause", rng.choice((1, 2, 2, 4))
    if kind == "fast":
        later = (_move(rng) if rng.random() < 0.4 else None for _ in range(rng.randint(0, 3)))
        gaps = (None, *later)
        return "fast", rng.choice((1, 2, 2)), gaps
    return "note", rng.choice((1, 1, 2, 2, 3, 4)), kind == "vibrato"


def _body(rng: random.Random, size: int) -> tuple:
    """What a repeat or motif holds: leaves with a move between some. It starts on a note, ends on a
    note or a pause, and a pause never has a move before it."""
    items = [_leaf(rng, pause_ok=False)]
    for _ in range(size - 1):
        leaf = _leaf(rng, pause_ok=True)
        if leaf[0] != "pause" and rng.random() < 0.75:
            items.append(("move", *_move(rng)))
        items.append(leaf)
    return tuple(items)


def _span(recipe: tuple) -> tuple[int, int]:
    """The lowest and highest note of a recipe, as levels from the one it starts on."""
    dry = _Writer(None)
    dry.walk(recipe)
    levels = [event.level for event in dry.events if event.kind != "pause"]
    return min(levels), max(levels)


class _Writer:
    """Writes phrases and plans their events. With no `rng` it only walks, to measure a recipe."""

    def __init__(self, rng: random.Random | None):
        self.rng = rng
        self.events: list[PlannedEvent] = []
        self.labels: dict[int, tuple[tuple, int]] = {}  # motif label -> body, hymn level of its plain uses
        self.index = 0  # the phrase being written
        self.level = 0  # the hymn level of the last note or pause
        self.previous: int | None = None  # the last note's level, whatever came between (rule 10)
        self.syllable = -1
        self.sliding = False  # a smooth, non-zero move waits for the next note
        self.after_note = False  # the last event was a note

    # -- phrases

    def phrase(self, index: int) -> PhraseString:
        """A phrase: a join or a new chain, then 3 to 10 recipes, each with the move that reaches it."""
        rng = self.rng
        self.index = index
        if index == 0 or rng.random() < 0.3:  # no join: a new chain
            recipe, start = self.opener()
            self.level, self.sliding, tokens = start, False, []
        else:
            recipe, start = self.pick(first=True)
            tokens = [self.lead(start - self.level) or "="]  # a join with no change is `=` or a bare tick
        tokens.append(self.walk(recipe))
        for _ in range(min(rng.randint(2, 9), rng.randint(2, 9))):  # 3 to 10 recipes, leaning short
            recipe, start = self.pick()
            if recipe[0] != "pause" and (move := self.lead(start - self.level)):
                tokens.append(move)
            tokens.append(self.walk(recipe))
        direction = "rtl" if rng.random() < 0.2 else "ltr"
        return PhraseString(phrase_id=f"p{index + 1}", direction=direction, notation=" ".join(tokens))

    def opener(self) -> tuple[tuple, int]:
        """A new chain's first recipe and the level its first note sits on (rule 5). A chain that shares
        a motif opens with it, so its offset is that motif's level plus its shift. Any other chain has
        offset 0."""
        if self.labels and self.rng.random() < 0.7:
            label = self.rng.choice(sorted(self.labels))
            body, home = self.labels[label]
            shift = self.rng.choice((0, 0, 0, 1, -1, 2, -2))
            recipe = ("motif", label, shift, body)
            start = self.start_of(recipe, home + shift)
            if start is not None:
                return recipe, start
        return self.pick(forced=0, first=True)

    def pick(self, forced: int | None = None, first: bool = False) -> tuple[tuple, int]:
        """A random recipe that fits, and the level its first note sits on."""
        for _ in range(8):
            recipe = self.recipe(first)
            start = self.start_of(recipe, forced)
            if start is not None:
                return recipe, start
        return ("note", 2, False), self.level if forced is None else forced

    def recipe(self, first: bool) -> tuple:
        """A random recipe. A motif may use a label already heard, which keeps it on that label's level."""
        rng = self.rng
        kind = rng.choices(("leaf", "repeat", "motif"), (5, 2, 3))[0]
        if kind == "repeat":
            step = rng.choice((0, 0, 1, 1, -1, 2, -2))  # levels per copy
            return "repeat", _body(rng, rng.randint(1, 2)), rng.randint(2, 3), step
        if kind == "motif":
            label = rng.randint(1, 5)
            if label in self.labels:
                return "motif", label, rng.choice((0, 0, 0, 1, -1, 2, -2)), self.labels[label][0]
            return "motif", label, 0, _body(rng, rng.randint(2, 3))
        return _leaf(rng, pause_ok=not first)

    def start_of(self, recipe: tuple, forced: int | None) -> int | None:
        """The level a recipe's first note sits on, or None if it can't sit where it must or won't fit
        the range. `forced` fixes it for a new chain. A label already heard fixes it too, at its level
        plus the shift."""
        if recipe[0] == "pause":
            return self.level
        low, high = _span(recipe)
        start = forced
        if recipe[0] == "motif" and recipe[1] in self.labels:
            start = self.labels[recipe[1]][1] + recipe[2]
            if forced not in (None, start) or (forced is None and abs(start - self.level) > 4):
                return None
        elif start is None:
            start = min(max(self.level + self.rng.choice((-2, -1, 0, 0, 1, 2)), LOW - low), HIGH - high)
        return start if LOW - low <= start <= HIGH - high else None

    def lead(self, change: int) -> str:
        """The move that reaches a level `change` away, a slope or a corner. With no change, nothing or a
        bare tick."""
        if change:
            return self.move(self.rng.random() < 0.3, change)
        return self.move(True, 0) if self.rng.random() < 0.25 else ""

    # -- walking a recipe

    def walk(self, recipe: tuple, lyrics: bool = True) -> str:
        """The text of a recipe, planning its events on the way. `lyrics` is off in later repeat copies."""
        match recipe:
            case ("note", length, vibrato):
                kind = "vibrato" if vibrato else "note"
                return self.note(Fraction(length), kind, "~" * vibrato + str(length), lyrics)
            case ("pause", length):
                pause = PlannedEvent(self.index, "pause", Fraction(length), 0, None, None, False)
                self.events.append(pause)
                self.after_note = False
                return f".{length}"
            case ("move", abrupt, change):
                return self.move(abrupt, change)
            case ("fast", length, gaps):  # the beads split the length evenly
                parts = []
                for gap in gaps:
                    if gap:
                        parts.append(self.move(*gap))
                    parts.append(self.note(Fraction(length, len(gaps)), "fast", "*", lyrics))
                return ">" + str(length) + "{" + " ".join(parts) + "}"
            case ("repeat", body, count, step):
                start, copies = self.level, []
                for copy in range(count):
                    if copy:  # copy i starts at start + i * step, by a smooth move of whatever size
                        self.move(False, start + copy * step - self.level)
                    copies.append(self.body(body, lyrics and copy == 0))
                return f"({copies[0]})x{count}{_arrow(step)}"  # the text holds one copy
            case ("motif", label, shift, body):
                self.labels.setdefault(label, (body, self.level - shift))
                tag = f"#{label}{shift:+d}" if shift else f"#{label}"
                return f"{tag}[{self.body(body, lyrics)}]"
        raise ValueError(f"unknown recipe {recipe!r}")

    def body(self, items: tuple, lyrics: bool) -> str:
        return " ".join(self.walk(item, lyrics) for item in items)

    def move(self, abrupt: bool, change: int) -> str:
        self.level += change
        self.sliding = not abrupt and change != 0
        return ("!" if abrupt else "") + _arrow(change)

    def note(self, length: Fraction, kind: str, tail: str, lyrics: bool) -> str:
        label, starts = self.lyric(lyrics)
        if starts:
            self.syllable += 1
        cause = "syllable_start" if starts else "pitch_change" if self.level != self.previous else "resung"
        slides_in = self.sliding and self.after_note
        self.events.append(
            PlannedEvent(self.index, kind, length, self.level, self.syllable, cause, slides_in)
        )
        self.previous, self.sliding, self.after_note = self.level, False, True
        return label + tail

    def lyric(self, on: bool) -> tuple[str, bool]:
        """What stands before a note: a new syllable, a vowel label or nothing. The hymn's first note
        starts a syllable. Returns the text and whether it starts one."""
        if not on or self.rng is None:
            return "", False
        roll = self.rng.random()
        if self.syllable < 0 or roll < 0.4:
            return self.rng.choice(SYLLABLES) + ":", True
        if roll < 0.55:
            return f"({self.rng.choice(VOWELS)}):", False
        return "", False
