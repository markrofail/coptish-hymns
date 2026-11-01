"""Round-trip check: compares the string with the recording and the text."""

from hymnstring.contracts import RoundTripInput, RoundTripReport
from hymnstring.harness import Node, not_built

NODE = Node("round_trip_check", RoundTripInput, RoundTripReport, not_built)
