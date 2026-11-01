import copy
import json
import re
import unicodedata
from pathlib import Path

import pytest
from pydantic import ValidationError

import hymnstring.contracts as contracts

EXAMPLES = Path(__file__).parent.parent / "fixtures" / "contracts"
SCHEMAS = {name: getattr(contracts, name) for name in contracts.__all__ if name != "Contract"}


def file_name(schema_name):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", schema_name).lower() + ".json"


def example(schema_name):
    return json.loads((EXAMPLES / file_name(schema_name)).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", SCHEMAS)
def test_example_file_is_valid_and_complete(name):
    payload = example(name)

    assert SCHEMAS[name].model_validate(payload).model_dump(mode="json") == payload


def test_every_example_file_belongs_to_a_schema():
    assert {path.name for path in EXAMPLES.glob("*.json")} == {file_name(name) for name in SCHEMAS}


def test_unknown_fields_are_rejected():
    payload = example("PulseUnit") | {"bpm": 120}

    with pytest.raises(ValidationError):
        contracts.PulseUnit.model_validate(payload)


def test_contracts_cannot_be_changed_after_validation():
    pulse = contracts.PulseUnit.model_validate(example("PulseUnit"))

    with pytest.raises(ValidationError):
        pulse.source = "cymbals"


def set_at(payload, path, value):
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value


# schema, what is broken, path into its example, value that breaks it
BROKEN = [
    ("HymnText", "no text", ["text"], "   "),
    ("HymnText", "unknown tradition", ["tradition"], "sahidic"),
    ("Recording", "no path", ["path"], ""),
    ("SeparationInput", "unknown backend", ["backend"], "spleeter"),
    ("Voice", "no length", ["duration_s"], 0),
    ("Voice", "no sample rate", ["sample_rate_hz"], 0),
    ("Voice", "unknown backend", ["backend"], "spleeter"),
    ("Voice", "bypass with an accompaniment", ["accompaniment_path"], "work/demo/other.flac"),
    ("Voice", "separated with no accompaniment", ["backend"], "roformer"),
    ("PreparedText", "syllables out of order", ["syllables", 1, "index"], 2),
    ("PreparedText", "text not NFC", ["syllables", 0, "text"], unicodedata.normalize("NFD", "ϊ")),
    ("PreparedText", "lines leave a gap", ["lines", 0, "last_syllable"], 0),
    ("PreparedText", "lines overlap", ["lines", 0, "last_syllable"], 2),
    ("PreparedText", "a line runs backwards", ["lines", 1, "last_syllable"], 1),
    ("PreparedText", "lines stop short", ["lines", 1, "last_syllable"], 3),
    ("PreparedText", "repeat of a later line", ["lines", 0, "repeat_of"], 1),
    ("PreparedText", "repeat of itself", ["lines", 1, "repeat_of"], 1),
    ("PreparedText", "verses go backwards", ["lines", 0, "verse_index"], 1),
    ("PreparedText", "no fingerprint", ["fingerprint"], ""),
    ("Sounds", "syllables out of order", ["syllables", 1, "syllable_index"], 4),
    ("Sounds", "no romanised form", ["syllables", 0, "romanised"], ""),
    ("Sounds", "romanised with a macron", ["syllables", 0, "romanised"], "lē"),
    ("Sounds", "romanised with a capital", ["syllables", 0, "romanised"], "A"),
    ("Sounds", "romanised with a space", ["syllables", 0, "romanised"], "a b"),
    ("Sounds", "a syllable with no sounds", ["syllables", 0, "sounds"], []),
    ("Sounds", "flag before the syllable", ["syllables", 0, "added"], [{"position": -1, "letter": "ⲉ"}]),
    ("PitchTrack", "frames disagree", ["confidence"], [1.0]),
    ("PitchTrack", "zero pitch instead of null", ["f0_hz", 0], 0),
    ("PitchTrack", "confidence above one", ["confidence", 0], 1.5),
    ("PitchTrack", "no hop", ["hop_s"], 0),
    ("PitchTrack", "vibrato ends before it starts", ["vibrato", 0, "end_s"], 0.0),
    ("PulseUnit", "no sections", ["sections"], []),
    ("PulseUnit", "zero unit", ["sections", 0, "half_note_s"], 0),
    ("PulseUnit", "section ends before it starts", ["sections", 0, "end_s"], 0.0),
    ("StepSize", "no sections", ["sections"], []),
    ("StepSize", "zero step", ["sections", 0, "step_cents"], 0),
    ("StepSize", "confidence above one", ["sections", 0, "confidence"], 1.5),
    ("SyllableTimes", "ends before it starts", ["syllables", 0, "end_s"], 0.0),
    ("SyllableTimes", "syllables out of order", ["syllables", 1, "syllable_index"], 4),
    ("SyllableTimes", "start goes back in time", ["syllables", 1, "start_s"], 0.5),
    ("SyllableTimes", "confidence below zero", ["syllables", 0, "confidence"], -0.1),
    ("NoteStarts", "notes go back in time", ["notes", 1, "start_s"], 0.0),
    ("NoteStarts", "note before the recording", ["notes", 0, "start_s"], -1.0),
    ("NoteStarts", "unknown cause", ["notes", 0, "cause"], "semitone"),
    ("NoteStarts", "breath ends before it starts", ["breaths", 0, "end_s"], 3.0),
    ("Patterns", "a single occurrence", ["patterns", 0, "occurrences"], [{"start_s": 0.0, "end_s": 2.0}]),
    ("Patterns", "unknown kind", ["patterns", 0, "kind"], "similar"),
    ("HymnString", "no phrases", ["phrases"], []),
    ("HymnString", "unknown direction", ["phrases", 0, "direction"], "up"),
    ("HymnString", "empty notation", ["phrases", 0, "notation"], ""),
    ("HymnString", "notation runs over two lines", ["phrases", 0, "notation"], "1\n1"),
    ("HymnString", "unknown format version", ["format_version"], 2),
    ("HymnString", "alias signs in the notation", ["phrases", 0, "notation"], "1 ↑ 2"),
    ("HymnString", "notation that does not parse", ["phrases", 0, "notation"], "1 ^^ 2 ("),
    ("HymnString", "notation with a structural problem", ["phrases", 0, "notation"], "1 ^"),
    ("RoundTripReport", "passed with errors", ["phrases", 0, "errors"], ["syllable 3 missing"]),
    ("RoundTripReport", "failed with no error", ["phrases", 0, "passed"], False),
    ("RoundTripReport", "negative pitch error", ["phrases", 0, "pitch_error_cents"], -1.0),
    ("RoundTripReport", "drift with no estimate", ["steps", 0, "estimated_cents"], None),
    ("ReviewRecord", "a fix that changes nothing", ["after"], "1 ^ 2"),
    ("ReviewRecord", "after is not canonical", ["after"], "2 ↑ 2"),
    ("ReviewRecord", "before does not parse", ["before"], "2 ^^"),
    ("ReviewRecord", "no phrase", ["phrase_id"], ""),
    ("ReviewRecord", "unknown format version", ["format_version"], 2),
    ("LibraryEntry", "another hymn's fix", ["corrections", 0, "fingerprint"], "other"),
    ("RenderedPage", "no page", ["html_path"], ""),
]


@pytest.mark.parametrize(
    "name, path, value",
    [row[0:1] + row[2:] for row in BROKEN],
    ids=[f"{row[0]}: {row[1]}" for row in BROKEN],
)
def test_broken_payload_is_rejected(name, path, value):
    payload = copy.deepcopy(example(name))
    set_at(payload, path, value)

    with pytest.raises(ValidationError):
        SCHEMAS[name].model_validate(payload)


def test_romanised_form_accepts_an_apostrophe():
    payload = example("Sounds")
    payload["syllables"][0]["romanised"] = "l'e"

    sounds = contracts.Sounds.model_validate(payload)

    assert sounds.syllables[0].romanised == "l'e"


def test_repeated_phrase_ids_are_rejected():
    payload = example("HymnString")
    payload["phrases"].append(payload["phrases"][0])

    with pytest.raises(ValidationError):
        contracts.HymnString.model_validate(payload)


@pytest.mark.parametrize(
    "name, section",
    [
        ("PulseUnit", {"start_s": 5.0, "end_s": 12.0, "half_note_s": 0.4, "confidence": 0.9}),
        ("StepSize", {"start_s": 5.0, "end_s": 12.0, "step_cents": 150.0, "confidence": 0.9}),
    ],
    ids=["PulseUnit", "StepSize"],
)
def test_overlapping_sections_are_rejected(name, section):
    payload = example(name)
    payload["sections"].append(section)

    with pytest.raises(ValidationError):
        SCHEMAS[name].model_validate(payload)


def test_separation_is_bypassed_unless_a_backend_is_chosen():
    separation = contracts.SeparationInput.model_validate({"recording": {"path": "hymn.flac"}})

    assert separation.backend == "bypass"


def test_a_separated_voice_keeps_its_accompaniment():
    payload = example("Voice") | {"backend": "demucs", "accompaniment_path": "work/demo/other.flac"}

    voice = contracts.Voice.model_validate(payload)

    assert voice.accompaniment_path == "work/demo/other.flac"


def test_a_section_with_no_stable_intervals_has_no_step():
    payload = example("StepSize")
    payload["sections"][0]["step_cents"] = None

    step = contracts.StepSize.model_validate(payload)

    assert step.sections[0].step_cents is None


def test_a_section_with_no_estimate_has_no_drift():
    payload = example("RoundTripReport")
    payload["steps"][0] |= {"estimated_cents": None, "drift_cents": None}

    report = contracts.RoundTripReport.model_validate(payload)

    assert report.steps[0].drift_cents is None


def test_failed_phrase_keeps_its_errors():
    payload = example("RoundTripReport")
    payload["phrases"][0] |= {"passed": False, "errors": ["syllable 3 missing"]}

    report = contracts.RoundTripReport.model_validate(payload)

    assert report.phrases[0].errors == ("syllable 3 missing",)


def test_a_line_may_repeat_an_earlier_line():
    payload = example("PreparedText")
    payload["lines"][1]["repeat_of"] = 0

    text = contracts.PreparedText.model_validate(payload)

    assert text.lines[1].repeat_of == 0


def test_letters_from_both_coptic_blocks_and_a_jinkim_are_accepted():
    payload = example("PreparedText")
    payload["syllables"][0]["text"] = "ⲛ̀ϣ"

    text = contracts.PreparedText.model_validate(payload)

    assert text.syllables[0].text == "ⲛ̀ϣ"
