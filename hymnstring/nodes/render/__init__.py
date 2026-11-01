"""Render: draws the string view, synced to the audio."""

from hymnstring.contracts import RenderInput, RenderedPage
from hymnstring.harness import Node, not_built

NODE = Node("render", RenderInput, RenderedPage, not_built)
