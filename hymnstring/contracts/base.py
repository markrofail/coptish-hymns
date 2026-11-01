"""The base every contract shares, and the small types they are built from."""

import unicodedata
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator


def _is_nfc(text: str) -> str:
    if unicodedata.normalize("NFC", text) != text:
        raise ValueError("text must be NFC-normalised")
    return text


NonEmpty = Annotated[str, Field(pattern=r"\S")]
Nfc = Annotated[NonEmpty, AfterValidator(_is_nfc)]
OneLine = Annotated[str, Field(pattern=r"^[^\r\n]+$")]
Index = Annotated[int, Field(ge=0)]
Seconds = Annotated[float, Field(ge=0)]
Positive = Annotated[float, Field(gt=0)]
Score = Annotated[float, Field(ge=0, le=1)]


class Contract(BaseModel):
    """Data passed along an edge of the graph: immutable, no unknown fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Empty(Contract):
    """Carries nothing. Used by the empty node."""


class TimeSpan(Contract):
    start_s: Seconds
    end_s: Seconds

    @model_validator(mode="after")
    def ends_after_it_starts(self) -> Self:
        if self.end_s <= self.start_s:
            raise ValueError("must end after it starts")
        return self


def require_counting_up(indices: list[int], what: str) -> None:
    if indices != list(range(len(indices))):
        raise ValueError(f"{what} must count up from 0 with no gaps")
