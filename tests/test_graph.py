"""The graph drawn in CONTEXT.md section 4, checked against what nodes declare."""

import importlib
import re
import subprocess
import sys
from pathlib import Path
from typing import get_args

import pytest

import hymnstring.contracts as contracts
import hymnstring.nodes

ROOT = Path(__file__).parent.parent

# The Mermaid id of each graph node.
NODE_IDS = {
    "SEP": "separation",
    "TP": "text_prep",
    "PR": "pronunciation",
    "PC": "pitch_contour",
    "PU": "pulse_unit",
    "ON": "note_onsets",
    "LA": "lyric_aligner",
    "ST": "step_size",
    "PM": "pattern_miner",
    "HI": "hazzat_interpreter",
    "RT": "round_trip_check",
    "RE": "render",
}

# What reaches a node from outside the nodes themselves.
OUTSIDE = {
    "R": contracts.Recording,
    "T": contracts.HymnText,
    "HL": contracts.LibraryEntry,
}

EDGE = re.compile(r'^(?P<source>\w+)(?:[\[(].*?[\])])?\s*-\.?->\s*(?:\|"[^"]*"\|\s*)?(?P<target>\w+)')


def node(name):
    return importlib.import_module(f"hymnstring.nodes.{name}").NODE


def drawn_edges():
    diagram = (ROOT / "CONTEXT.md").read_text(encoding="utf-8").split("```mermaid")[1].split("```")[0]
    matches = (EDGE.match(line.strip()) for line in diagram.splitlines())
    return {(match["source"], match["target"]) for match in matches if match}


def carried_by(source):
    return OUTSIDE[source] if source in OUTSIDE else node(NODE_IDS[source]).output


def producer_of(contract):
    return next(source for source in [*NODE_IDS, *OUTSIDE] if carried_by(source) is contract)


def takes(schema):
    """The contracts a node takes: its input, or the fields of a bundled input."""
    if schema.__module__ != "hymnstring.contracts.inputs":
        return {schema}
    options = [
        option
        for field in schema.model_fields.values()
        for option in (field.annotation, *get_args(field.annotation))
    ]
    return {o for o in options if isinstance(o, type) and issubclass(o, contracts.Contract)}


def test_every_graph_node_has_a_folder():
    folders = {path.parent.name for path in Path(hymnstring.nodes.__file__).parent.glob("*/__init__.py")}

    assert folders == set(NODE_IDS.values()) | {"empty"}


@pytest.mark.parametrize("name", sorted(NODE_IDS.values()))
def test_node_knows_its_own_name(name):
    assert node(name).name == name


@pytest.mark.parametrize(
    "source, target",
    sorted(edge for edge in drawn_edges() if edge[1] in NODE_IDS),
    ids=lambda mermaid_id: mermaid_id,
)
def test_drawn_edge_carries_a_contract_the_target_takes(source, target):
    assert carried_by(source) in takes(node(NODE_IDS[target]).input)


@pytest.mark.parametrize("target", sorted(NODE_IDS))
def test_every_input_of_a_node_is_drawn(target):
    sources = {source for source, to in drawn_edges() if to == target}

    undrawn = {
        contract.__name__
        for contract in takes(node(NODE_IDS[target]).input)
        if producer_of(contract) not in sources | {target}
    }

    assert undrawn == set()


def test_library_keeps_the_fixes_from_cantor_review():
    assert contracts.LibraryEntry.model_fields["corrections"].annotation == tuple[contracts.ReviewRecord, ...]


@pytest.mark.parametrize("name", sorted(NODE_IDS.values()))
def test_node_rejects_bad_input_from_the_command_line(name):
    done = subprocess.run(
        [sys.executable, "-m", f"hymnstring.nodes.{name}"],
        input='{"unexpected": 1}',
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert done.returncode == 2, done.stderr
    assert done.stdout == ""


def test_unbuilt_node_stops_after_checking_its_input():
    example = ROOT / "fixtures" / "contracts" / "hymn_text.json"

    done = subprocess.run(
        [sys.executable, "-m", "hymnstring.nodes.text_prep", "--in", str(example)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert done.returncode == 1
    assert "NotImplementedError" in done.stderr
