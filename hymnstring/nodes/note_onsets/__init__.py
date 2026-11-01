"""Note onsets: where notes and breaths start inside each syllable."""

from hymnstring.contracts import NoteStarts, OnsetsInput
from hymnstring.harness import Node, not_built

NODE = Node("note_onsets", OnsetsInput, NoteStarts, not_built)
