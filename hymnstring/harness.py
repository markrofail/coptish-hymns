"""Runs a node: JSON in, JSON out, with the contract checked on both sides."""

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from hymnstring.contracts import Contract


class ContractError(Exception):
    """Data at a node's edge doesn't match its contract."""


@dataclass(frozen=True)
class Node:
    name: str
    input: type[Contract]
    output: type[Contract]
    run: Callable[[Any], Any]


def not_built(given: Any) -> Any:
    raise NotImplementedError("this node isn't built yet")


def run_node(node: Node, payload: Any) -> dict:
    try:
        given = node.input.model_validate(payload)
    except ValidationError as error:
        raise ContractError(f"{node.name}: bad input: {error}") from error

    result = node.run(given)
    if isinstance(result, BaseModel):
        result = result.model_dump(mode="json")
    try:
        return node.output.model_validate(result).model_dump(mode="json")
    except ValidationError as error:
        raise ContractError(f"{node.name}: bad output: {error}") from error


def cli(node: Node, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=f"hymnstring.nodes.{node.name}")
    parser.add_argument("--in", dest="source", type=Path, help="default: stdin")
    parser.add_argument("--out", dest="target", type=Path, help="default: stdout")
    args = parser.parse_args(argv)

    raw = args.source.read_text(encoding="utf-8") if args.source else sys.stdin.read()
    try:
        output = run_node(node, json.loads(raw))
    except json.JSONDecodeError as error:
        print(f"{node.name}: input is not JSON: {error}", file=sys.stderr)
        return 2
    except ContractError as error:
        print(error, file=sys.stderr)
        return 2

    text = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    if args.target:
        args.target.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0
