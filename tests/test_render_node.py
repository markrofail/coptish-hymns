import json
import subprocess
import sys
from pathlib import Path

from hymnstring.contracts import HymnString

FIXTURE = Path(__file__).parent.parent / "fixtures" / "contracts" / "render_input.json"


def run_render(payload):
    return subprocess.run(
        [sys.executable, "-m", "hymnstring.nodes.render"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_render_writes_the_page_and_returns_its_path(tmp_path):
    out = tmp_path / "not" / "yet" / "page.html"  # the folder doesn't exist
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["out_path"] = str(out)

    done = run_render(payload)

    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout) == {"html_path": str(out)}
    page = out.read_text(encoding="utf-8")
    assert page.count('class="bead"') == 13
    assert "ⲗⲟⲩ" in page


def test_fixture_string_is_valid():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    string = HymnString.model_validate(payload["string"])

    assert string.text.startswith("p1 ltr: #1[ⲁ:2")


def test_empty_out_path_is_a_contract_error():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["out_path"] = ""

    done = run_render(payload)

    assert done.returncode == 2
    assert "out_path" in done.stderr


def test_an_unwritable_out_path_is_a_contract_error_and_not_a_traceback(tmp_path):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["out_path"] = str(tmp_path)  # an existing folder

    done = run_render(payload)

    assert done.returncode == 2
    assert "Traceback" not in done.stderr
    assert str(tmp_path) in done.stderr
