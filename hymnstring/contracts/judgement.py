"""Patterns, the string itself, and what happens to it afterwards."""

from typing import Literal, Self

from pydantic import Field, model_validator

from hymnstring.contracts.base import Contract, NonEmpty, OneLine, Positive, Score, TimeSpan

FormatVersion = Literal[1]


class Pattern(Contract):
    pattern_id: NonEmpty
    kind: Literal["exact", "near", "rising", "falling"]
    seed: Literal["text", "library", "audio"]
    score: Score
    occurrences: tuple[TimeSpan, ...] = Field(min_length=2)


class Patterns(Contract):
    patterns: tuple[Pattern, ...]


class PhraseString(Contract):
    """One phrase. `notation` is the text form in hymnstring/notation/SPEC.md."""

    phrase_id: NonEmpty
    direction: Literal["ltr", "rtl"]
    notation: OneLine


class HymnString(Contract):
    format_version: FormatVersion
    phrases: tuple[PhraseString, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def phrase_ids_are_unique(self) -> Self:
        ids = [phrase.phrase_id for phrase in self.phrases]
        if len(ids) != len(set(ids)):
            raise ValueError("phrase ids must be unique")
        return self


class PhraseCheck(Contract):
    phrase_id: NonEmpty
    passed: bool
    pitch_error_cents: float | None = Field(ge=0)
    errors: tuple[NonEmpty, ...]

    @model_validator(mode="after")
    def failing_means_having_an_error(self) -> Self:
        if self.passed == bool(self.errors):
            raise ValueError("a phrase fails exactly when it has errors")
        return self


class StepCheck(TimeSpan):
    """The step estimate for a section, and how far the refit moved it (refit minus estimate)."""

    estimated_cents: Positive | None
    drift_cents: float | None

    @model_validator(mode="after")
    def drift_needs_an_estimate(self) -> Self:
        if self.estimated_cents is None and self.drift_cents is not None:
            raise ValueError("drift needs an estimate to drift from")
        return self


class RoundTripReport(Contract):
    steps: tuple[StepCheck, ...]
    phrases: tuple[PhraseCheck, ...]


class ReviewRecord(Contract):
    """One cantor fix; caused_by is filled in once it is traced to a node."""

    format_version: FormatVersion
    fingerprint: NonEmpty
    phrase_id: NonEmpty
    before: OneLine
    after: OneLine
    comment: str
    reviewer: NonEmpty
    caused_by: NonEmpty | None

    @model_validator(mode="after")
    def a_fix_changes_something(self) -> Self:
        if self.before == self.after:
            raise ValueError("a fix must change the notation")
        return self


class LibraryEntry(Contract):
    fingerprint: NonEmpty
    strings: tuple[HymnString, ...]
    corrections: tuple[ReviewRecord, ...]

    @model_validator(mode="after")
    def corrections_belong_to_this_hymn(self) -> Self:
        if any(fix.fingerprint != self.fingerprint for fix in self.corrections):
            raise ValueError("every correction must belong to this hymn")
        return self


class RenderedPage(Contract):
    html_path: NonEmpty
