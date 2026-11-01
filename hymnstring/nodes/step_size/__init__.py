"""Step size: how big one level is, per section."""

from hymnstring.contracts import StepInput, StepSize
from hymnstring.harness import Node, not_built

NODE = Node("step_size", StepInput, StepSize, not_built)
