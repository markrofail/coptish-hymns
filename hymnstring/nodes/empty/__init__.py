"""Does nothing. Shows the harness works end to end."""

from hymnstring.contracts import Empty
from hymnstring.harness import Node

NODE = Node("empty", Empty, Empty, lambda given: given)
