import json
import subprocess
import sys
import wave
from pathlib import Path

from hymnstring.contracts import SynthOutput

FIXTURE = Path(__file__).parent.parent / "fixtures" / "contracts" / "synth_input.json"


def job(out_path, notation=None, **settings):
    """The fixture's demo phrase (13 notes, 22 half notes of 0.5 s), with any changes asked for."""
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["out_path"] = str(out_path)
    if notation is not None:
        payload["string"]["phrases"][0]["notation"] = notation
    payload["settings"] |= settings
    return payload


def run_synth(payload, timeout=None):
    return subprocess.run(
        [sys.executable, "-m", "hymnstring.synth"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
    )


def recording_of(tmp_path, name, **settings):
    """The bytes of the file that a successful run writes."""
    done = run_synth(job(tmp_path / name, **settings))
    assert done.returncode == 0, done.stderr
    return (tmp_path / name).read_bytes()


def test_the_node_writes_a_recording_and_returns_the_true_values(tmp_path):
    out = tmp_path / "not" / "yet" / "sung.wav"  # the folder doesn't exist

    done = run_synth(job(out))

    assert done.returncode == 0, done.stderr
    output = SynthOutput.model_validate_json(done.stdout)
    voice = output.voice
    assert (voice.path, voice.sample_rate_hz) == (str(out), 16000)
    assert voice.duration_s == 11.0  # 22 half notes of 0.5 s
    assert (voice.backend, voice.accompaniment_path) == ("bypass", None)  # the file is what is heard next
    with wave.open(str(out), "rb") as wav:
        assert wav.getnframes() == round(voice.duration_s * voice.sample_rate_hz) == 176000
        assert wav.getframerate() == voice.sample_rate_hz
    assert len(output.truth.note_starts.notes) == 13


def test_two_runs_write_identical_bytes(tmp_path):
    noisy = {"seed": 3, "noise_snr_db": 20.0}  # the noise is random, so the seed has to settle it

    first = recording_of(tmp_path, "first.wav", **noisy)
    second = recording_of(tmp_path, "second.wav", **noisy)
    other_seed = recording_of(tmp_path, "other.wav", **(noisy | {"seed": 4}))

    assert first == second
    assert other_seed != first  # so the identity above isn't just a node that leaves the noise out


def test_bad_input_is_exit_2():
    done = run_synth({"unexpected": 1})

    assert done.returncode == 2, done.stderr
    assert done.stdout == ""


def test_an_absurd_length_is_exit_2_and_quick(tmp_path):
    done = run_synth(job(tmp_path / "huge.wav", "a:999999999"), timeout=20)

    assert done.returncode == 2, done.stderr
    assert "Traceback" not in done.stderr
    assert "1800" in done.stderr


def test_a_string_with_no_first_syllable_is_exit_2(tmp_path):
    done = run_synth(job(tmp_path / "mute.wav", "2"))

    assert done.returncode == 2, done.stderr
    assert "syllable" in done.stderr


def test_an_unwritable_out_path_is_exit_2(tmp_path):
    done = run_synth(job(tmp_path))  # an existing folder

    assert done.returncode == 2, done.stderr
    assert "Traceback" not in done.stderr
    assert str(tmp_path) in done.stderr


def test_a_section_past_the_end_is_exit_2(tmp_path):
    out = tmp_path / "later" / "sung.wav"
    payload = job(out)
    # the demo has one phrase, and phrases count from 0
    payload["settings"]["sections"].append({"first_phrase": 1, "half_note_s": 0.5, "step_cents": 200.0})

    done = run_synth(payload)

    assert done.returncode == 2, done.stderr
    assert not out.parent.exists()  # nothing is made until the singing has worked
