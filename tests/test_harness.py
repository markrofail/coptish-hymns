import json
import subprocess
import sys

import pytest

from hymnstring.contracts import Contract, Empty
from hymnstring.harness import ContractError, Node, cli, run_node


class Word(Contract):
    text: str


def run_module(name, *args, stdin=""):
    return subprocess.run(
        [sys.executable, "-m", f"hymnstring.nodes.{name}", *args],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_empty_node_runs_from_stdin_to_stdout():
    done = run_module("empty", stdin="{}")

    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout) == {}


def test_empty_node_runs_from_file_to_file(tmp_path):
    source = tmp_path / "in.json"
    target = tmp_path / "out.json"
    source.write_text("{}", encoding="utf-8")

    done = run_module("empty", "--in", str(source), "--out", str(target))

    assert done.returncode == 0, done.stderr
    assert done.stdout == ""
    assert json.loads(target.read_text(encoding="utf-8")) == {}


def test_input_that_breaks_the_contract_stops_the_node():
    done = run_module("empty", stdin='{"unexpected": 1}')

    assert done.returncode == 2
    assert done.stdout == ""
    assert "empty" in done.stderr


def test_input_that_is_not_json_stops_the_node():
    done = run_module("empty", stdin="not json")

    assert done.returncode == 2
    assert done.stdout == ""


def test_a_rejected_input_never_reaches_the_node():
    calls = []
    node = Node("word", Word, Word, lambda given: calls.append(given) or given)

    with pytest.raises(ContractError):
        run_node(node, {"text": 7})

    assert calls == []


def test_node_gets_its_input_as_the_contract_type():
    node = Node("shout", Word, Word, lambda given: Word(text=given.text.upper()))

    assert run_node(node, {"text": "ⲁ"}) == {"text": "Ⲁ"}


@pytest.mark.parametrize(
    "bad_output",
    [Empty(), {"text": 7}, None],
    ids=["wrong contract", "wrong field type", "nothing"],
)
def test_output_that_breaks_the_contract_is_caught(bad_output):
    node = Node("liar", Word, Word, lambda given: bad_output)

    with pytest.raises(ContractError):
        run_node(node, {"text": "ⲁ"})


def test_an_input_file_that_cannot_be_read_stops_the_node(tmp_path, capsys):
    unreadable = tmp_path / "bad.json"
    unreadable.write_bytes(b"\xff\xfe{}")
    node = Node("same", Word, Word, lambda given: given)

    for source in (tmp_path / "missing.json", unreadable):
        assert cli(node, ["--in", str(source)]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.count("same") == 2


def test_coptic_stays_readable_in_the_output_file(tmp_path):
    source = tmp_path / "in.json"
    target = tmp_path / "out.json"
    source.write_text('{"text": "ϣⲁ"}', encoding="utf-8")
    node = Node("same", Word, Word, lambda given: given)

    status = cli(node, ["--in", str(source), "--out", str(target)])

    assert status == 0
    assert "ϣⲁ" in target.read_text(encoding="utf-8")
