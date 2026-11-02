"""Render: turns the string into an HTML page and writes it to `out_path`. The audio sync comes in Phase 3."""

from pathlib import Path

from hymnstring.contracts import RenderedPage, RenderInput
from hymnstring.harness import ContractError, Node
from hymnstring.notation import parse_hymn, render_hymn


def run(given: RenderInput) -> RenderedPage:
    page = render_hymn(parse_hymn(given.string.text))
    out = Path(given.out_path)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page, encoding="utf-8")
    except OSError as error:
        raise ContractError(f"render: cannot write out_path {given.out_path!r}: {error}") from error
    return RenderedPage(html_path=given.out_path)


NODE = Node("render", RenderInput, RenderedPage, run)
