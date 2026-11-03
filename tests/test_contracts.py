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
    ("PitchTrack", "infinite pitch", ["f0_hz", 1], float("inf")),
    (
        "PitchTrack",
        "vibratos overlap",
        ["vibrato"],
        [
            {"start_s": 2.0, "end_s": 3.0, "rate_hz": 5.5, "width_cents": 60.0},
            {"start_s": 2.5, "end_s": 3.5, "rate_hz": 5.5, "width_cents": 60.0},
        ],
    ),
    ("PitchTrack", "vibrato ends before it starts", ["vibrato", 0, "end_s"], 0.0),
    ("PulseUnit", "no sections", ["sections"], []),
    ("PulseUnit", "zero unit", ["sections", 0, "half_note_s"], 0),
    ("PulseUnit", "infinite unit", ["sections", 0, "half_note_s"], float("inf")),
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
    ("NoteStarts", "syllable index goes back", ["notes", 4, "syllable_index"], 0),
    (
        "NoteStarts",
        "breaths overlap",
        ["breaths"],
        [{"start_s": 3.0, "end_s": 4.0}, {"start_s": 3.5, "end_s": 4.5}],
    ),
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
    ("HymnString", "phrase id that smuggles a second phrase", ["phrases", 0, "phrase_id"], "a ltr: 1\nb"),
    ("HymnString", "phrase id with a space", ["phrases", 0, "phrase_id"], "p 1"),
    ("RoundTripReport", "passed with errors", ["phrases", 0, "errors"], ["syllable 3 missing"]),
    ("RoundTripReport", "failed with no error", ["phrases", 0, "passed"], False),
    ("RoundTripReport", "negative pitch error", ["phrases", 0, "pitch_error_cents"], -1.0),
    ("RoundTripReport", "drift is not a number", ["steps", 0, "drift_cents"], float("nan")),
    ("RoundTripReport", "drift is infinite", ["steps", 0, "drift_cents"], float("inf")),
    ("RoundTripReport", "phrase id with a space", ["phrases", 0, "phrase_id"], "p 1"),
    ("RoundTripReport", "drift with no estimate", ["steps", 0, "estimated_cents"], None),
    ("ReviewRecord", "a fix that changes nothing", ["after"], "1 ^ 2"),
    ("ReviewRecord", "after is not canonical", ["after"], "2 ↑ 2"),
    ("ReviewRecord", "after ends on a move", ["after"], "1 ^"),
    ("ReviewRecord", "after repeats once", ["after"], "(1)x1"),
    ("ReviewRecord", "before has two moves in a row", ["before"], "1 ^ ^ 1"),
    ("ReviewRecord", "phrase id with a space", ["phrase_id"], "p 1"),
    ("ReviewRecord", "before does not parse", ["before"], "2 ^^"),
    ("ReviewRecord", "no phrase", ["phrase_id"], ""),
    ("ReviewRecord", "unknown format version", ["format_version"], 2),
    ("InterpreterInput", "a last try with no report", ["last_report"], None),
    ("InterpreterInput", "a last report with no try", ["last_try"], None),
    ("LibraryEntry", "another hymn's fix", ["corrections", 0, "fingerprint"], "other"),
    ("RenderedPage", "no page", ["html_path"], ""),
    ("SynthSettings", "no sections", ["sections"], []),
    ("SynthSettings", "first section starts late", ["sections", 0, "first_phrase"], 1),
    ("SynthSettings", "sections out of order", ["sections", 1, "first_phrase"], 0),
    ("SynthSettings", "half note under 10 ms", ["sections", 0, "half_note_s"], 0.001),
    ("SynthSettings", "step of two and a bit octaves", ["sections", 0, "step_cents"], 2401),
    ("SynthSettings", "zero step", ["sections", 0, "step_cents"], 0),
    ("SynthSettings", "negative seed", ["seed"], -1),
    ("SynthSettings", "wobble above one half", ["timing_wobble"], 0.6),
    ("SynthSettings", "sample rate too low", ["sample_rate_hz"], 4000),
    ("SynthSettings", "cymbals every zero", ["cymbal_every"], 0),
    ("SynthSettings", "no reverberation time", ["echo_rt60_s"], 0),
    ("SynthSettings", "sample rate too high", ["sample_rate_hz"], 48001),
    ("SynthSettings", "hop under a millisecond", ["hop_s"], 0.0005),
    ("SynthSettings", "hop over a second", ["hop_s"], 1.5),
    ("SynthSettings", "negative wobble", ["timing_wobble"], -0.1),
    ("SynthSettings", "drift above an octave a minute", ["drift_cents_per_min"], 1201),
    ("SynthSettings", "drift below an octave a minute", ["drift_cents_per_min"], -1201),
    ("SynthSettings", "reverberation over ten seconds", ["echo_rt60_s"], 10.5),
    ("SynthSettings", "no base pitch", ["base_hz"], 0),
    ("SynthSettings", "no slope", ["slope_s"], 0),
    ("SynthSettings", "no vibrato rate", ["vibrato_rate_hz"], 0),
    ("SynthSettings", "no vibrato width", ["vibrato_width_cents"], 0),
    ("SynthSettings", "infinite noise level", ["noise_snr_db"], float("inf")),
    ("SynthSettings", "noise over 40 dB louder than the voice", ["noise_snr_db"], -41),
    ("SynthSettings", "noise over 120 dB quieter than the voice", ["noise_snr_db"], 121),
    ("SynthSettings", "echo over 80 dB below the voice", ["echo_wet_db"], -81),
    ("SynthSettings", "echo over 20 dB above the voice", ["echo_wet_db"], 21),
    ("SynthSettings", "cymbals over 80 dB below the voice", ["cymbal_db"], -81),
    ("SynthSettings", "cymbals over 40 dB above the voice", ["cymbal_db"], 41),
    ("SynthInput", "no out_path", ["out_path"], ""),
    ("SynthInput", "a string that does not parse", ["string", "phrases", 0, "notation"], "1 ^^"),
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


def test_a_last_try_and_its_report_may_come_together():
    payload = example("InterpreterInput")
    payload["last_try"] = example("HymnString")
    payload["last_report"] = example("RoundTripReport")

    given = contracts.InterpreterInput.model_validate(payload)

    assert given.last_try is not None and given.last_report is not None


def test_a_first_try_has_neither():
    payload = example("InterpreterInput") | {"last_try": None, "last_report": None}

    given = contracts.InterpreterInput.model_validate(payload)

    assert given.last_try is None and given.last_report is None


def test_a_fix_may_start_with_a_join_or_a_shifted_motif():
    payload = example("ReviewRecord") | {"before": "= 1", "after": "#1+1[1]"}

    fix = contracts.ReviewRecord.model_validate(payload)

    assert fix.after == "#1+1[1]"


def test_a_seed_and_a_tempo_are_enough_and_the_rest_is_a_clean_tone():
    section = {"first_phrase": 0, "half_note_s": 0.5, "step_cents": 200.0}

    settings = contracts.SynthSettings.model_validate({"seed": 1, "sections": [section]})

    assert settings.model_dump(mode="json") == {
        "seed": 1,
        "sections": [section],
        "base_hz": 130.0,
        "sample_rate_hz": 16000,
        "hop_s": 0.01,
        "slope_s": 0.08,
        "vibrato_rate_hz": 5.5,
        "vibrato_width_cents": 100.0,
        "timing_wobble": 0.0,
        "drift_cents_per_min": 0.0,
        "noise_snr_db": None,
        "echo_rt60_s": None,
        "echo_wet_db": -6.0,
        "cymbal_every": None,
        "cymbal_db": 0.0,
    }


@pytest.mark.parametrize(
    "path",
    [["seed"], ["sections"], ["sections", 0, "first_phrase"], ["sections", 0, "half_note_s"], ["sections", 0, "step_cents"]],
    ids=lambda path: ".".join(map(str, path)),
)
def test_a_run_has_to_say_what_it_means(path):
    payload = copy.deepcopy(example("SynthSettings"))
    target = payload
    for key in path[:-1]:
        target = target[key]
    del target[path[-1]]

    with pytest.raises(ValidationError):
        contracts.SynthSettings.model_validate(payload)


@pytest.mark.parametrize(
    "settings, section",
    [
        (
            {
                "sample_rate_hz": 8000, "hop_s": 0.001, "timing_wobble": 0, "drift_cents_per_min": -1200,
                "noise_snr_db": -40, "echo_wet_db": -80, "cymbal_db": -80,
            },
            {"half_note_s": 0.01, "step_cents": 0.001},
        ),
        (
            {
                "sample_rate_hz": 48000, "hop_s": 1, "timing_wobble": 0.5, "drift_cents_per_min": 1200,
                "noise_snr_db": 120, "echo_wet_db": 20, "cymbal_db": 40,
            },
            {"half_note_s": 100, "step_cents": 2400},
        ),
        ({"echo_rt60_s": 0.001, "cymbal_every": 1}, {}),
        ({"echo_rt60_s": 10}, {}),
    ],
    ids=["lowest", "highest", "smallest echo and cymbal grid", "longest echo"],
)
def test_the_ends_of_every_range_are_allowed(settings, section):
    payload = copy.deepcopy(example("SynthSettings")) | settings
    payload["sections"][0] |= section

    contracts.SynthSettings.model_validate(payload)
