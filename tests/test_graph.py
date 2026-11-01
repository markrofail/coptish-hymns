"""The edges drawn in CONTEXT.md section 4, checked against what nodes declare."""

import importlib
import subprocess
import sys
from pathlib import Path
from typing import get_args

import pytest

import hymnstring.contracts as contracts
import hymnstring.nodes

GRAPH_NODES = {
    "separation",
    "text_prep",
    "pronunciation",
    "pitch_contour",
    "pulse_unit",
    "note_onsets",
    "lyric_aligner",
    "pattern_miner",
    "hazzat_interpreter",
    "round_trip_check",
    "render",
}

# from, to, contract carried
EDGES = [
    ("text_prep", "pronunciation", contracts.PreparedText),
    ("separation", "pitch_contour", contracts.Voice),
    ("separation", "pulse_unit", contracts.Voice),
    ("separation", "note_onsets", contracts.Voice),
    ("separation", "lyric_aligner", contracts.Voice),
    ("pronunciation", "lyric_aligner", contracts.Sounds),
    ("lyric_aligner", "note_onsets", contracts.SyllableTimes),
    ("pitch_contour", "pattern_miner", contracts.PitchTrack),
    ("pulse_unit", "pattern_miner", contracts.PulseUnit),
    ("note_onsets", "pattern_miner", contracts.NoteStarts),
    ("lyric_aligner", "pattern_miner", contracts.SyllableTimes),
    ("text_prep", "pattern_miner", contracts.PreparedText),
    ("pattern_miner", "hazzat_interpreter", contracts.Patterns),
    ("hazzat_interpreter", "round_trip_check", contracts.HymnString),
    ("text_prep", "round_trip_check", contracts.PreparedText),
    ("round_trip_check", "hazzat_interpreter", contracts.RoundTripReport),
]


def node(name):
    return importlib.import_module(f"hymnstring.nodes.{name}").NODE


def accepts(schema, wanted):
    """Whether a node's input is `wanted`, or has a field holding `wanted`."""
    if schema is wanted:
        return True
    for field in schema.model_fields.values():
        if wanted is field.annotation or wanted in get_args(field.annotation):
            return True
    return False


def test_every_graph_node_has_a_folder():
    folders = {path.parent.name for path in Path(hymnstring.nodes.__file__).parent.glob("*/__init__.py")}

    assert folders == GRAPH_NODES | {"empty"}


@pytest.mark.parametrize("name", sorted(GRAPH_NODES))
def test_node_knows_its_own_name(name):
    assert node(name).name == name


@pytest.mark.parametrize(
    "source, target, contract",
    EDGES,
    ids=[f"{source} > {target}" for source, target, _ in EDGES],
)
def test_edge_carries_its_contract(source, target, contract):
    assert node(source).output is contract
    assert accepts(node(target).input, contract)


def test_library_reaches_the_interpreter():
    assert accepts(node("hazzat_interpreter").input, contracts.LibraryEntry)


def test_library_keeps_the_fixes_from_cantor_review():
    assert contracts.LibraryEntry.model_fields["corrections"].annotation == tuple[contracts.ReviewRecord, ...]


def test_round_trip_result_reaches_render():
    assert accepts(node("render").input, contracts.HymnString)
    assert accepts(node("render").input, contracts.RoundTripReport)


@pytest.mark.parametrize("name", sorted(GRAPH_NODES))
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
    example = Path(__file__).parent.parent / "fixtures" / "contracts" / "hymn_text.json"

    done = subprocess.run(
        [sys.executable, "-m", "hymnstring.nodes.text_prep", "--in", str(example)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert done.returncode == 1
    assert "NotImplementedError" in done.stderr
