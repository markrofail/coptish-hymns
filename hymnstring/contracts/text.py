"""The text side: the hymn as given, its syllables and their sung sounds."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from hymnstring.contracts.base import Contract, Index, Nfc, NonEmpty, require_counting_up

# The alphabet of torchaudio's MMS_FA aligner: lowercase a-z and the apostrophe.
Romanised = Annotated[str, Field(pattern=r"^[a-z']+$")]

Tradition = Literal["greco_bohairic", "old_bohairic"]


class HymnText(Contract):
    """Input to text prep. Lines are separated by newlines."""

    text: NonEmpty
    tradition: Tradition


class Syllable(Contract):
    index: Index
    text: Nfc
    word_index: Index
    is_greek: bool
    implied_vowel: str | None


class Line(Contract):
    index: Index
    verse_index: Index
    text: Nfc
    first_syllable: Index
    last_syllable: Index
    repeat_of: Index | None

    @model_validator(mode="after")
    def repeats_an_earlier_line(self) -> Self:
        if self.repeat_of is not None and self.repeat_of >= self.index:
            raise ValueError("a line can only repeat an earlier line")
        return self


class PreparedText(Contract):
    """Text prep's output: syllable order, repeated lines and hymn identity."""

    fingerprint: NonEmpty
    tradition: Tradition
    syllables: tuple[Syllable, ...]
    lines: tuple[Line, ...]

    @model_validator(mode="after")
    def lines_cover_every_syllable_once(self) -> Self:
        require_counting_up([syllable.index for syllable in self.syllables], "syllable indices")
        require_counting_up([line.index for line in self.lines], "line indices")
        covered = [
            index
            for line in self.lines
            for index in range(line.first_syllable, line.last_syllable + 1)
        ]
        if covered != [syllable.index for syllable in self.syllables]:
            raise ValueError("lines must cover every syllable once, in order")
        verses = [line.verse_index for line in self.lines]
        if verses != sorted(verses):
            raise ValueError("verses must be in order")
        return self


class LetterFlag(Contract):
    """A letter at a position in a syllable's text."""

    position: Index
    letter: Nfc


class SyllableSound(Contract):
    syllable_index: Index
    sounds: tuple[NonEmpty, ...] = Field(min_length=1)
    romanised: Romanised
    silent: tuple[LetterFlag, ...]
    added: tuple[LetterFlag, ...]


class Sounds(Contract):
    tradition: Tradition
    syllables: tuple[SyllableSound, ...]

    @model_validator(mode="after")
    def syllables_in_order(self) -> Self:
        require_counting_up([sound.syllable_index for sound in self.syllables], "syllable indices")
        return self
