"""The base every contract shares."""

from pydantic import BaseModel, ConfigDict


class Contract(BaseModel):
    """Data passed along an edge of the graph: immutable, no unknown fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Empty(Contract):
    """Carries nothing. Used by the empty node."""
