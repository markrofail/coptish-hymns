# Synthesiser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task by task.

**Goal:** Turn a string into a vowel-like sung tone with exact answers. PLAN.md Phase 0 item 5: settings for tempo, step size, vibrato, noise, room echo and cymbals; writes the true pitch track, note starts, syllable times, pulse unit and step size; done when those true values match the string exactly for 50 random strings.

**Architecture:** Two stages with one shared description. `hymnstring/synth/score.py` lays a string out in exact time and pitch, with no sound involved. `truth.py` reads the score into the five existing contracts, and `voice.py` and `room.py` read the same score into samples, through one pitch function, so the answers and the audio cannot disagree. `random_hymns.py` writes random strings alongside its own plan of what they mean, worked out without `flatten` or the score, so the 50-string check compares two independent derivations.

**Tech Stack:** Python 3.12, `numpy==1.26.4` (BSD-3-Clause), stdlib `wave`. numpy stays on 1.x because torch 2.2.2 and torchaudio 2.2.2, which Phase 2 needs, are built against it. No scipy.

**Spec:** PLAN.md Phase 0 item 5 and the "Tested with" line of each Phase 2 part; CONTEXT.md sections 2 and 3; `hymnstring/notation/SPEC.md`.

## Global Constraints

- Work on the `synthesiser` branch in `/Users/mark/workplace/coptish/coptish-string-notation`. Never touch `main`.
- Python 3.12 in `.venv`. Run tests with `.venv/bin/python -m pytest`. A hook called `rtk` rewrites some shell commands; prefix `rtk proxy` if a command is refused or its output is filtered.
- numpy is the only new dependency. Pin it in `pyproject.toml` and `requirements.lock`.
- Never commit audio. Tests write audio only under pytest's `tmp_path`, or keep it in memory.
- `hymnstring/notation/` must never import `hymnstring.contracts`, `hymnstring.synth` or numpy.
- The synthesiser is not a graph node. It lives in `hymnstring/synth/`, because `tests/test_graph.py` allows only graph nodes in `hymnstring/nodes/`.
- Don't change the fields of an existing contract. New contracts go in `hymnstring/contracts/synth.py`.
- "Hazzat steps and lengths are relative. Never quantise to semitones, absolute pitches or BPM." `step_cents` takes any positive value, tempo is seconds per half note, and nothing rounds a pitch to a scale.
- Follow TDD. Expected values are hand-derived literals or come from `random_hymns.py`'s plan. A test must never get its expected value from the code it checks.
- Match the surrounding code: short module docstrings, the comment density of `hymnstring/harness.py`, frozen dataclasses, no speculative options.
- The whole suite stays under 60 s. If it doesn't, make the measuring cheaper; never drop seeds.
- End every commit message with a `Co-Authored-By:` line naming the model that wrote the commit, as your own attribution instructions give it, followed by exactly this line:
  `Claude-Session: https://claude.ai/code/session_01G42KT8b6fHhNgrLamjj7z1`

## How a string becomes sound

These rules are numbered so tasks, tests and reviews can cite them.

**Time**

1. Phrases follow each other with no gap. The only silence is a pause in the string, and the echo tail after the last note.
2. An event lasts `half_note_s * length * wobble` seconds, using the section its phrase belongs to. Times are exact `Fraction`s built with `Fraction(half_note_s)`, so `float(time)` is the correctly rounded answer.
3. `wobble` is exactly 1 when `timing_wobble` is 0. Otherwise it is `Fraction(float(1 + rng.uniform(-w, w)))`, one draw per event in event order, pauses included. Wobble moves the true times. The true `half_note_s` stays the setting.
4. A hymn lasts at most `MAX_SECONDS = 1800`, or `build_score` raises `SynthError` naming the limit. A length such as `999999999` must fail at once, before anything is allocated.

**Levels and pitch**

5. A note's hymn level is its chain level (from `walk_chains`) plus its chain's offset. Keep `known`, a dict from motif label to the hymn level of its plain occurrences. For each chain in order: the first motif use in the chain whose label is in `known` sets `offset = known[label] + use.shift - use.start_level`; with none, `offset = 0`. Then, for every use in the chain in order, `known.setdefault(label, offset + use.start_level - use.shift)`. This keeps a motif at one pitch across chains, which the round-trip check will compare. If two motifs in a chain disagree, the first one wins.
6. Cents grow one section at a time, so a rise is always a rise. Section 0 has `origin_level = 0` and `origin_cents = 0`. Each later section takes `origin_level` from the hymn level of the previous section's last note, and `origin_cents` from that note's `raw_cents`. A section with no notes keeps the origin it was given. Within a section, `raw_cents = origin_cents + (level - origin_level) * step_cents`.
7. `SungNote.cents` is `raw_cents` minus the lowest `raw_cents` in the hymn, so a note's pitch is `base_hz * 2 ** (cents / 1200)` and `base_hz` is the hymn's lowest note.
8. The highest pitch reached must stay under half the sample rate: `log2(base_hz) + (max_cents + vibrato_width_cents / 2 + max(0, drift_cents_per_min) * end_seconds / 60) / 1200 < log2(sample_rate_hz / 2)`, checked in logs so that a huge level can't overflow. Otherwise `build_score` raises `SynthError` naming the sample rate.

**Notes**

9. A `Syllable` lyric starts a new syllable, numbered from 0 in order of appearance. Any other note carries on the current one, including across phrases. A `Vowel` label is not a new syllable. If the hymn's first note has no `Syllable` lyric, `build_score` raises `SynthError` saying the first note must start a syllable, because every true note names its syllable.
10. `cause` is `syllable_start` if the note starts a syllable; otherwise `pitch_change` if its hymn level differs from the previous note's, pauses in between or not; otherwise `resung`. Compare levels, not moves, so a new chain and a bare `!` are handled by the same rule.
11. `slides_on` is true on a note when the very next event is a note, and the move into that next note is smooth with a non-zero change. That move is `FlatNote.move`, or the phrase's join for a phrase's first note. A repeat's joins are smooth moves in `flatten`. There is no slide after a pause, into an abrupt move, or into a phrase with no join.
12. Adjacent pauses are one `Rest`. A trailing pause counts toward the end of the hymn.

**The pitch curve**

13. `pitch_at(score, settings, times)` is the one function that gives pitch. It returns Hz per time, and NaN where no note is sounding. A note sounds from `float(start)` up to but not including `float(end)`.
14. A slide takes the last `g = min(slope_s, (end - start) / 2)` seconds of its note and is linear in cents, reaching the next note's cents at the next note's start. An abrupt move steps at the note's start.
15. A vibrato note adds `vibrato_width_cents / 2 * sin(2π * vibrato_rate_hz * (t - note_start))` cents over the whole note, slide included. So `width_cents` is peak to peak.
16. Drift adds `drift_cents_per_min * t / 60` cents to every note. It stays out of `SungNote.cents`.

**The voice**

17. Samples are at `n / sample_rate_hz`. `sample_count(score, settings)` is `ceil(end * rate)`, plus `ceil(echo_rt60_s * rate)` when echo is on, both computed exactly with `Fraction`.
18. The source is `sum(sin(k * phase) / k)` for `k` up to `MAX_HARMONICS = 30`, where `phase` is the running sum of `2π * f0 / rate` and each harmonic is left out wherever `k * f0` reaches half the sample rate.
19. An "ah" shape is applied once to the whole source, in the frequency domain with no phase change (`rfft`, multiply, `irfft`): `H(f) = 0.15 + sum(gain * exp(-0.5 * ((f - centre) / width) ** 2))` with `FORMANTS = ((730, 90, 1.0), (1090, 110, 0.7), (2440, 170, 0.3))`.
20. Loudness multiplies the shaped source last, so that silence is exactly 0.0. It is 1 while sounding and 0 otherwise, with a linear ramp of `min(RAMP_S, note / 2)` (`RAMP_S = 0.01`) at the start and end of each unbroken run of notes. Both ramps sit inside the note, so loudness at a run's first sample is 0.
21. A note that follows another with no rest and has cause `resung` or `syllable_start` gets a dip centred on its start: multiply by `1 - DIP_DEPTH * 0.5 * (1 + cos(π * (t - start) / h))` for `|t - start| < h`, with `DIP_DEPTH = 0.9` and `h = min(DIP_S, previous_note / 3, this_note / 3)`, `DIP_S = 0.015`. This is what makes a re-sung note audible. A `pitch_change` note has no dip: its pitch is the cue.

**The room**

22. Each random source has its own generator, `np.random.default_rng([seed, PURPOSE])`, with `PURPOSE` one of `TIMING = 0`, `NOISE = 1`, `ECHO = 2`, `CYMBALS = 3`. So turning one source on never changes another. The same seed gives identical samples.
23. The mix is `voice + cymbals`, then echo, then noise. All levels are relative to `voice_rms`, the RMS of the voice's non-zero samples.
24. Cymbals are on when `cymbal_every` is set. Each section hits at `section.start + k * cymbal_every * half_note_s`, while that is before `section.end`. Timing wobble doesn't move the hits. A hit is `CYMBAL_HIT_S = 0.4` seconds of `np.diff` of white noise, times `exp(-t / 0.08)`, scaled so that its peak is `voice_rms * 10 ** (cymbal_db / 20)`.
25. Echo is on when `echo_rt60_s` is set. The response is 1 at time 0, followed by white noise times `10 ** (-3 * t / rt60)`, for `ceil(rt60 * rate)` samples. The noise part is scaled so its total energy is `10 ** (echo_wet_db / 10)`. Convolve by FFT and cut to `sample_count`.
26. Noise is on when `noise_snr_db` is set. It is white, runs over the whole recording, and is scaled so its RMS is exactly `voice_rms * 10 ** (-noise_snr_db / 20)`.
27. `Synthesis.samples` is the raw float mix. `write_wav` writes mono 16-bit PCM with its peak at `0.9` of full scale.

**The true values**

28. Every `confidence` is 1.0, except a silent pitch frame's, which is 0.0.
29. `PitchTrack`: one frame at `i * hop_s` for each `i` in `range(ceil(duration / hop_s))`, with `duration = sample_count / rate`, both exact. `f0_hz` is `pitch_at` at those times, None for NaN. `vibrato` has one span per vibrato note, its start to its end, with the settings' rate and width.
30. `NoteStarts`: one per note, plus `breaths` from the rests. `SyllableTimes`: each syllable runs from its first note's start to its last note's end, so a pause inside a syllable is inside its span, and `catch_all` is empty. `PulseUnit` and `StepSize`: one section each per `SynthSection`, from the section's first event to the next section's start, or the hymn's end for the last. `PulseUnit.source` is `cymbals` when cymbals are on, otherwise `note_durations`.

## Review Focus

1. An absurd length, `a:999999999`, or a climb out of range, `a:1 ^99999999 1`: a clear `SynthError`, at once, with no allocation or overflow. Tests in Tasks 1 and 6.
2. Answers that match the string but not the sound: if a true value isn't in the audio, Phase 2 tunes against a lie. Tests in Tasks 4 and 5 measure the audio with code that shares nothing with the synthesiser.
3. The edges of a phrase: a trailing pause, a join after a trailing pause, an `=` join, a new chain with no lyric, a repeat whose body ends on a pause, and adjacent pauses. Tests in Task 1.
4. One random source disturbing another: turning noise on must leave the voice untouched, and the same seed must give identical bytes. Tests in Task 5.
5. A section boundary where the step changes: a rising join must still rise, and each section's span must end where the next begins. Tests in Task 1.

---

### Task 1: Contracts, the chain walk and the score

**Files:**
- Modify: `pyproject.toml`, `requirements.lock`
- Modify: `hymnstring/notation/flatten.py`, `hymnstring/notation/validator.py`, `hymnstring/notation/__init__.py`
- Create: `hymnstring/contracts/synth.py`; `fixtures/contracts/synth_settings.json`, `synth_input.json`, `ground_truth.json`, `synth_output.json`
- Modify: `hymnstring/contracts/__init__.py`, `tests/test_contracts.py`
- Create: `hymnstring/synth/__init__.py`, `hymnstring/synth/score.py`
- Test: `tests/test_notation_flatten.py`, `tests/test_synth_score.py`

**Interfaces:**
- Produces, in `hymnstring/notation/flatten.py` and exported from `hymnstring.notation`:
  - `ChainedPhrase(index: int, phrase: Phrase, chain: int, flat: Flat)`, a frozen dataclass. `chain` counts from 0.
  - `walk_chains(hymn: Hymn, items_of: Callable[[Phrase], tuple[Item, ...]] = <phrase.items>) -> Iterator[ChainedPhrase]`. The first phrase, or a phrase with no join, starts a new chain at level 0. A `Move` join adds its change to the last phrase's `end_level`, and `SameLevel` adds nothing.
- Produces, in `hymnstring/contracts/synth.py`:
  - `SynthSection(first_phrase: Index, half_note_s: float >= 0.01, step_cents: float > 0 and <= 2400)`
  - `SynthSettings`: `seed: Index`, `sections: tuple[SynthSection, ...]` (at least one; first `first_phrase` is 0, then strictly rising), and these with defaults: `base_hz: Positive = 130.0`, `sample_rate_hz: int = 16000` (8000 to 48000), `hop_s: float = 0.01` (0.001 to 1), `slope_s: Positive = 0.08`, `vibrato_rate_hz: Positive = 5.5`, `vibrato_width_cents: Positive = 100.0`, `timing_wobble: float = 0.0` (0 to 0.5), `drift_cents_per_min: float = 0.0` (-1200 to 1200), `noise_snr_db: float | None = None`, `echo_rt60_s: float | None = None` (above 0, up to 10), `echo_wet_db: float = -6.0`, `cymbal_every: int | None = None` (half-note units, at least 1), `cymbal_db: float = 0.0`. Its docstring says the default is a clean tone, and that tempo and step have no default, so a run always says what it means.
  - `SynthInput(string: HymnString, settings: SynthSettings, out_path: NonEmpty)`
  - `GroundTruth(pitch_track: PitchTrack, note_starts: NoteStarts, syllable_times: SyllableTimes, pulse_unit: PulseUnit, step_size: StepSize)`
  - `SynthOutput(voice: Voice, truth: GroundTruth)`
  - Export `GroundTruth`, `SynthInput`, `SynthOutput` and `SynthSettings` from `hymnstring.contracts`. `SynthSection` stays out of `__all__`, like `PulseSection`.
- Produces, in `hymnstring/synth/score.py`, exported from `hymnstring.synth`:
  - `class SynthError(ValueError)`
  - `SungNote(start: Fraction, end: Fraction, level: int, cents: float, kind: Literal["note", "vibrato", "fast"], syllable: int, cause: Literal["syllable_start", "pitch_change", "resung"], slides_on: bool)`
  - `Rest(start: Fraction, end: Fraction)`
  - `TimedSection(start: Fraction, end: Fraction, half_note_s: float, step_cents: float)`
  - `Score(notes: tuple[SungNote, ...], rests: tuple[Rest, ...], sections: tuple[TimedSection, ...], end: Fraction)`
  - `build_score(hymn: Hymn, settings: SynthSettings) -> Score`, raising `SynthError` for rules 4, 8 and 9, and for a section whose `first_phrase` is past the last phrase.
  - `sample_count(score: Score, settings: SynthSettings) -> int` (rule 17)
  - `TIMING = 0`, `NOISE = 1`, `ECHO = 2`, `CYMBALS = 3`, `MAX_SECONDS = 1800`

- [ ] **Step 1: Add numpy.** Add `"numpy==1.26.4"` to `dependencies` in `pyproject.toml`, with a one-line comment that it stays on 1.x because torch 2.2.2 is built against it. Add it to `requirements.lock` after `iniconfig`. Run `.venv/bin/python -m pip install numpy==1.26.4` and check `.venv/bin/python -c "import numpy; print(numpy.__version__)"` prints `1.26.4`.

- [ ] **Step 2: Write failing tests for `walk_chains`** in `tests/test_notation_flatten.py`:

```python
def test_chains_share_levels_through_joins():
    hymn = parse_hymn("p1 ltr: 1 ^ 1\np2 ltr: v2 1\np3 ltr: = 1\np4 ltr: 1")

    walked = list(walk_chains(hymn))

    assert [w.chain for w in walked] == [0, 0, 0, 1]
    assert [[e.level for e in w.flat.events] for w in walked] == [[0, 1], [-1], [-1], [0]]
    assert [w.index for w in walked] == [0, 1, 2, 3]


def test_a_trailing_pause_holds_the_level_a_join_starts_from():
    hymn = parse_hymn("p1 ltr: 1 ^ 1 .2\np2 ltr: ^ 1")

    assert [w.flat.events[-1].level for w in walk_chains(hymn)] == [1, 2]
```

- [ ] **Step 3: Run them to see them fail, implement `walk_chains`, and change `validator._motifs` to use it,** passing `items_of=lambda phrase: _without_rising_motifs(phrase.items)[0]`. Every existing validator test must pass unchanged.

- [ ] **Step 4: Add the contracts and fixtures.** Write the failing cases first: add rows to `BROKEN` in `tests/test_contracts.py`:

```python
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
("SynthInput", "no out_path", ["out_path"], ""),
("SynthInput", "a string that does not parse", ["string", "phrases", 0, "notation"], "1 ^^"),
```

`synth_settings.json` has two sections, for the rows above. Every fixture lists every field, because `test_example_file_is_valid_and_complete` compares a full round trip. `synth_input.json` uses the one-phrase string from `render_input.json`, so its settings have one section, with `out_path` `work/demo/sung.wav`. `ground_truth.json` nests the existing `pitch_track`, `note_starts`, `syllable_times`, `pulse_unit` and `step_size` fixtures. `synth_output.json` is `voice.json` plus that truth.

- [ ] **Step 5: Write failing tests for `build_score`** in `tests/test_synth_score.py`, using this demo and helper:

```python
DEMO = "p1 ltr: #1[A:2 ^ 1 v 1] ^ lē:~2 .2 v (lou:1)x3^ >1{i:*} a:2 !v2 #1[(a):2 ^ 1 v 1] v 4"


def settings(half_note_s=0.5, step_cents=200.0, **more):
    return SynthSettings(
        seed=1,
        sections=(SynthSection(first_phrase=0, half_note_s=half_note_s, step_cents=step_cents),),
        **more,
    )


def score_of(text, **more):
    return build_score(parse_hymn(text), settings(**more))
```

The demo, by hand, from CONTEXT.md section 3 at 0.5 s per half note and 200 cents:

```python
def test_demo_times():
    score = score_of(DEMO)
    assert [float(n.start) for n in score.notes] == [0, 1, 1.5, 2, 4, 4.5, 5, 5.5, 6, 7, 8, 8.5, 9]
    assert [float(n.end) for n in score.notes] == [1, 1.5, 2, 3, 4.5, 5, 5.5, 6, 7, 8, 8.5, 9, 11]
    assert [(float(r.start), float(r.end)) for r in score.rests] == [(3, 4)]
    assert score.end == 11


def test_demo_pitch_follows_the_table_in_context():
    assert [n.cents for n in score_of(DEMO).notes] == [
        200, 400, 200, 400, 200, 400, 600, 600, 600, 200, 400, 200, 0,
    ]


def test_demo_syllables_and_causes():
    notes = score_of(DEMO).notes
    assert [n.syllable for n in notes] == [0, 0, 0, 1, 2, 2, 2, 3, 4, 4, 4, 4, 4]
    assert [n.cause for n in notes] == [
        "syllable_start", "pitch_change", "pitch_change", "syllable_start", "syllable_start",
        "pitch_change", "pitch_change", "syllable_start", "syllable_start", "pitch_change",
        "pitch_change", "pitch_change", "pitch_change",
    ]
    assert [n.kind for n in notes].count("vibrato") == 1 and notes[3].kind == "vibrato"
    assert notes[7].kind == "fast"


def test_demo_slides():
    assert [n.slides_on for n in score_of(DEMO).notes] == [
        True, True, True, False, True, True, False, False, False, True, True, True, False,
    ]
```

Chains (rule 5), each with `step_cents=200`:

| Test | Text | Expected `cents` |
| --- | --- | --- |
| `test_a_new_chain_starts_where_its_motif_already_sits` | `p1 ltr: a:1 ^ #1[1 ^ 1]` / `p2 ltr: b:1 ^2 #1[1 ^ 1]` | `[200, 400, 600, 0, 400, 600]` |
| `test_a_new_chain_with_no_shared_motif_starts_at_hymn_level_0` | `p1 ltr: a:1 ^ 1` / `p2 ltr: b:1 v 1` | `[200, 400, 200, 0]` |
| `test_a_shifted_motif_anchors_a_chain_at_its_shift` | `p1 ltr: a:1 #1[1]` / `p2 ltr: b:1 #1+2[1]` | `[0, 0, 400, 400]` |
| `test_the_first_motif_wins_when_two_disagree` | `p1 ltr: a:1 #1[1] ^ #2[1]` / `p2 ltr: b:1 #1[1] ^2 #2[1]` | `[0, 0, 200, 0, 0, 400]` |

Sections (rule 6), with `sections=(first_phrase 0, 0.5 s, 200 cents), (first_phrase 1, 0.25 s, 100 cents)` and text `p1 ltr: a:2 ^ 2` / `p2 ltr: ^ b:2 ^ 2`:

```python
def test_a_rise_stays_a_rise_when_the_step_changes():
    assert [n.cents for n in score.notes] == [0, 200, 300, 400]
    assert [float(n.start) for n in score.notes] == [0, 1, 2, 2.5]
    assert [(float(s.start), float(s.end)) for s in score.sections] == [(0, 2), (2, 3)]
    assert score.notes[1].slides_on  # a join between sections still slides
```

Edges of a phrase, each a test with literal values, at `half_note_s=0.5`:

| Test | Text | Expected |
| --- | --- | --- |
| `test_a_join_after_a_trailing_pause_does_not_slide` | `p1 ltr: a:2 .2` / `p2 ltr: ^ 2` | starts `[0, 2]`, end 3, causes `syllable_start, pitch_change`, no slides, rest `(1, 2)` |
| `test_an_equals_join_is_a_resung_note` | `p1 ltr: a:2` / `p2 ltr: = 2` | causes `syllable_start, resung`, syllables `[0, 0]`, no slides |
| `test_a_new_chain_with_no_lyric_keeps_the_syllable` | `p1 ltr: a:2` / `p2 ltr: 2` | causes `syllable_start, resung`, syllables `[0, 0]` |
| `test_a_new_chain_on_another_level_is_a_pitch_change` | `p1 ltr: a:2 ^ 2` / `p2 ltr: 2` | causes `syllable_start, pitch_change, pitch_change`, slides `T, F, F` |
| `test_a_repeat_whose_body_ends_on_a_pause` | `p1 ltr: (a:1 .1)x2^ 1` | levels `[0, 1, 1]`, causes `syllable_start, pitch_change, resung`, no slides, rests `(0.5, 1)` and `(1.5, 2)`, starts `[0, 1, 2]` |
| `test_adjacent_pauses_are_one_rest` | `p1 ltr: a:1 .2 .2 1` | rests `[(0.5, 2.5)]` |
| `test_a_bare_tick_is_a_resung_note` | `p1 ltr: a:1 ! 1` | causes `syllable_start, resung`, no slides |
| `test_a_new_syllable_on_the_same_level_is_a_syllable_start` | `p1 ltr: a:1 b:1` | causes `syllable_start, syllable_start` |
| `test_a_vowel_label_does_not_start_a_syllable` | `p1 ltr: a:1 (a):1` | syllables `[0, 0]`, causes `syllable_start, resung` |

Further tests:

```python
def test_fast_notes_split_their_length_exactly():
    score = score_of("p1 ltr: >2{ⲧⲓ:* ^ ⲛⲉ:* v ⲣⲁ:*}", half_note_s=0.6)
    assert score.notes[1].start == Fraction(0.6) * Fraction(2, 3)
    assert score.end == Fraction(0.6) * 2


def test_the_first_note_must_start_a_syllable():
    for text in ("p1 ltr: 2", "p1 ltr: (a):2"):
        with pytest.raises(SynthError, match="syllable"):
            score_of(text)


def test_a_section_past_the_last_phrase_is_an_error(): ...  # `first_phrase` 5 in a one-phrase hymn


def test_an_absurd_length_fails_at_once():
    with pytest.raises(SynthError, match="1800"):
        score_of("p1 ltr: a:999999999")


def test_a_hymn_exactly_at_the_limit_is_allowed():
    assert score_of("p1 ltr: a:1800", half_note_s=1.0).end == 1800


def test_a_climb_out_of_range_fails_without_overflowing():
    with pytest.raises(SynthError, match="sample rate"):
        score_of("p1 ltr: a:1 ^99999999 1", step_cents=2400.0)


def test_wobble_stays_within_its_bound_and_keeps_notes_touching():
    score = score_of("p1 ltr: a:2 2 2 2 2 2 2 2", timing_wobble=0.15)
    lengths = [float(n.end - n.start) for n in score.notes]
    assert all(0.85 <= length <= 1.15 for length in lengths)
    assert len(set(lengths)) == 8
    assert all(a.end == b.start for a, b in zip(score.notes, score.notes[1:]))
```

`test_the_same_seed_gives_the_same_wobble` and `test_another_seed_gives_another_wobble` go with those.

- [ ] **Step 6: Run them to see them fail, then implement `score.py`** from rules 1 to 12. Its module docstring states rule 1 and rule 5's "the first one wins", in a sentence each.

- [ ] **Step 7: Run the whole suite.** Expected: all pass, including every existing validator test unchanged.

- [ ] **Step 8: Commit.** `git commit -m "Add synthesiser contracts, the chain walk and the score"`

### Task 2: The true values

**Files:**
- Create: `hymnstring/synth/truth.py`
- Modify: `hymnstring/synth/__init__.py`, `hymnstring/contracts/audio.py` (docstring only)
- Test: `tests/test_synth_truth.py`

**Interfaces:**
- Consumes: `build_score`, `sample_count`, `Score`, `SungNote`, `Rest`, `TimedSection` from Task 1; `SynthSettings`, `GroundTruth`.
- Produces, in `hymnstring/synth/truth.py`:
  - `pitch_at(score: Score, settings: SynthSettings, times: np.ndarray) -> np.ndarray`: Hz per time, NaN when silent (rules 13 to 16). Vectorised with `np.searchsorted`.
  - `truth_of(score: Score, settings: SynthSettings) -> GroundTruth` (rules 28 to 30)
- Produces, exported from `hymnstring.synth`: `true_values(string: HymnString, settings: SynthSettings) -> GroundTruth`, which parses `string.text` and needs no audio.

- [ ] **Step 1: Write failing tests** in `tests/test_synth_truth.py`, all with `base_hz=100.0`:

```python
def at(score, cfg, *times):
    return pitch_at(score, cfg, np.array(times))


def test_notes_and_a_slide():
    # 0.5 s per half note, one octave per level, a slide over the last 0.1 s of the first note
    cfg = settings(half_note_s=0.5, step_cents=1200.0, base_hz=100.0, slope_s=0.1)
    score = build_score(parse_hymn("p1 ltr: a:2 ^ 2"), cfg)

    values = at(score, cfg, 0.5, 0.9, 0.95, 1.0, 1.99)
    assert values == pytest.approx([100, 100, 100 * 2**0.5, 200, 200])
    assert np.isnan(at(score, cfg, 2.0)[0])  # the end is not sounding


def test_a_slide_is_at_most_half_its_note():
    cfg = settings(half_note_s=0.2, step_cents=1200.0, base_hz=100.0, slope_s=0.08)
    score = build_score(parse_hymn("p1 ltr: >1{a:* ^ *}"), cfg)  # two notes of 0.1 s

    assert at(score, cfg, 0.05, 0.075) == pytest.approx([100, 100 * 2**0.5])


def test_an_abrupt_move_steps_at_the_note():
    cfg = settings(half_note_s=0.5, step_cents=1200.0, base_hz=100.0)
    score = build_score(parse_hymn("p1 ltr: a:2 !^ 2"), cfg)

    assert at(score, cfg, 0.99, 1.0) == pytest.approx([100, 200])


def test_vibrato_is_peak_to_peak():
    cfg = settings(half_note_s=0.5, base_hz=100.0, vibrato_rate_hz=5.0, vibrato_width_cents=100.0)
    score = build_score(parse_hymn("p1 ltr: a:~4"), cfg)

    assert at(score, cfg, 0.05, 0.15) == pytest.approx([100 * 2 ** (50 / 1200), 100 * 2 ** (-50 / 1200)])


def test_vibrato_carries_on_through_a_slide(): ...  # `a:~2 ^ 2`: cents are the slide's plus the vibrato's


def test_drift_adds_cents_over_time():
    cfg = settings(half_note_s=20.0, base_hz=100.0, drift_cents_per_min=120.0)
    score = build_score(parse_hymn("p1 ltr: a:4"), cfg)

    assert at(score, cfg, 30.0) == pytest.approx([100 * 2 ** (60 / 1200)])
```

The demo at 0.5 s and 200 cents, by hand:

```python
def test_demo_truth():
    truth = true_values(demo_string(), settings())

    assert [n.start_s for n in truth.note_starts.notes] == [0, 1, 1.5, 2, 4, 4.5, 5, 5.5, 6, 7, 8, 8.5, 9]
    assert [(b.start_s, b.end_s) for b in truth.note_starts.breaths] == [(3, 4)]
    assert [(s.start_s, s.end_s) for s in truth.syllable_times.syllables] == [
        (0, 2), (2, 3), (4, 5.5), (5.5, 6), (6, 11),
    ]
    assert truth.syllable_times.catch_all == ()
    assert [(s.start_s, s.end_s, s.half_note_s, s.confidence) for s in truth.pulse_unit.sections] == [(0, 11, 0.5, 1)]
    assert truth.pulse_unit.source == "note_durations"
    assert [(s.start_s, s.end_s, s.step_cents, s.confidence) for s in truth.step_size.sections] == [(0, 11, 200, 1)]


def test_demo_pitch_track():
    track = true_values(demo_string(), settings()).pitch_track

    assert track.hop_s == 0.01
    assert len(track.f0_hz) == 1100
    silent = [i for i, f0 in enumerate(track.f0_hz) if f0 is None]
    assert silent == list(range(300, 400))
    assert all(track.confidence[i] == (0.0 if i in silent else 1.0) for i in range(1100))
    assert [(v.start_s, v.end_s, v.rate_hz, v.width_cents) for v in track.vibrato] == [(2, 3, 5.5, 100)]
```

Also: `test_the_echo_tail_is_framed_and_silent` (`echo_rt60_s=0.5` on the demo: 1150 frames, the last 50 are None, and the note starts don't change), `test_cymbals_change_the_pulse_source` (`cymbal_every=2`), `test_a_pause_inside_a_syllable_is_inside_its_span` (`a:2 .2 2`: one syllable `(0, 3)` at 0.5 s, one breath `(1, 2)`), and `test_two_sections_give_two_true_sections`, using Task 1's two-section case, asserting `half_note_s` and `step_cents` per section and the spans `(0, 2)` and `(2, 3)`.

- [ ] **Step 2: Run them to see them fail, then implement `truth.py`** and `true_values`. Add to the `Vibrato` docstring in `hymnstring/contracts/audio.py` that `width_cents` is peak to peak. Change nothing else there.

- [ ] **Step 3: Run the whole suite.** Expected: all pass.

- [ ] **Step 4: Commit.** `git commit -m "Write the synthesiser's true values from the score"`

### Task 3: Random hymns and the 50-string check

This task holds the milestone's "Done when".

**Files:**
- Create: `hymnstring/synth/random_hymns.py`
- Modify: `hymnstring/synth/__init__.py`
- Test: `tests/test_synth_random.py`

**Interfaces:**
- Consumes: `HymnString`, `PhraseString`, `SynthSettings`, `SynthSection`; `true_values` from Task 2.
- Produces, in `hymnstring/synth/random_hymns.py`, exported from `hymnstring.synth`:
  - `PlannedEvent(phrase: int, kind: Literal["note", "vibrato", "fast", "pause"], length: Fraction, level: int, syllable: int | None, cause: str | None, slides_in: bool)`. `length` is in half-note units. `level` is the hymn level. `slides_in` means a smooth, non-zero move arrives at this note directly from a note before it. A pause has `level`, `syllable`, `cause` of `0`, `None`, `None` and `slides_in` False.
  - `RandomHymn(string: HymnString, events: tuple[PlannedEvent, ...])`
  - `random_hymn(seed: int) -> RandomHymn`
  - `random_settings(seed: int, phrases: int) -> SynthSettings`

**The generator's one rule:** it must not import `flatten`, `walk_chains`, `hymnstring.synth.score` or `truth`. It builds each hymn from a list of small recipes and walks them once, producing the text and the planned events together. It works out levels, repeat copies, joins, syllable numbers, causes and chain offsets with its own arithmetic. That independence is what the check rests on. Use stdlib `random.Random(seed)`.

What it must generate:

- 1 to 4 phrases of 3 to 10 items, ids `p1`, `p2`, ..., mostly `ltr` with some `rtl`. About 10 to 60 events a hymn. Keep every note's hymn level between -5 and 5, so that a hymn spans at most 10 levels and stays in a singing range.
- Each later phrase has a move join, an abrupt join, an `=` join, or no join.
- Canonical text only: a size or step of 1 is left out. `HymnString` rejects anything else, so its validation is the generator's first check.
- The hymn's first note has a syllable. Syllables come from a small list of Coptic letters, some with `<+ⲉ>` or `<-ϩ>` marks, and some notes have vowel labels such as `(ⲁ)`.
- Motif recipes are fixed once per label for a hymn, so every occurrence has the same shape. Later occurrences may carry different lyrics. A motif is placed by writing the move that reaches its required level; if no move is needed it is written with no move or with a bare `!`.
- Plain occurrences sit on one hymn level, across chains too, and shifted ones are that many levels from it. Follow rule 5 by construction: a chain that shares a motif with an earlier chain opens with that motif, so its offset is known from its first note. Any other chain has offset 0. Later motifs in a chain are placed to agree with its offset.

`random_settings`: use `random.Random(seed + 1_000_000)`. 1 to 3 sections at random phrase boundaries, never more than `phrases`, `half_note_s` uniform in 0.15 to 0.5, `step_cents` in 80 to 240, `base_hz` in 100 to 180, `vibrato_rate_hz` in 4.5 to 6.5, `vibrato_width_cents` in 60 to 140. Every other setting stays at its default.

- [ ] **Step 1: Write the failing coverage test.** Across seeds 0 to 49, the texts together must contain every token in SPEC.md's table. Name each as a regex in a table and assert each matches at least one hymn. Include a plain note, `~n`, `.n`, a fast group, a fast group with a move inside, a fast group crossing syllables, `^`, `v`, `^n`, `vn`, `!`, `!^` or `!v`, `!vn`, `xN`, `xN^`, `xNv`, `xN^K` or `xNvK`, `#n[`, `#n+k[` or `#n-k[`, a syllable, a vowel label, `<+`, `<-`, a join, an `=` join, and a phrase with no join after the first phrase. Add `test_a_motif_is_shared_across_chains` (some seed has a label in two chains), `test_the_same_seed_gives_the_same_hymn`, and `test_another_seed_gives_another_hymn`.

- [ ] **Step 2: Run it to see it fail, then implement `random_hymns.py`.**

- [ ] **Step 3: Write the 50-string check,** `test_true_values_match_the_string`, parametrised over `range(50)`. A helper in the test file, `worked_out(hymn, settings)`, computes the answers from `hymn.events` and the settings alone, and must not import `build_score`, `pitch_at`, `flatten` or `walk_chains`. It walks the events with exact `Fraction` time per rules 1 and 2, assigns sections from `PlannedEvent.phrase`, applies rule 6 and 7 for cents, and applies rule 12 to rests. Assert with `==`, not approx, on every time:

  - note starts, causes and syllable indices;
  - breaths;
  - syllable spans;
  - pulse sections (spans, `half_note_s`) and step sections (spans, `step_cents`);
  - vibrato spans, rate and width.

  Then walk every frame of the pitch track in plain Python (no numpy, no `pitch_at`), and assert None in silence and `pytest.approx(expected, rel=1e-12)` otherwise, applying rules 13 to 15. Assert the frame count from rules 17 and 29.

- [ ] **Step 4: Run it and fix what disagrees.** A disagreement is a bug in the score or in the generator. Find which by reading the rules, and don't weaken an assertion to pass.

- [ ] **Step 5: Prove the check can fail.** Temporarily make each of these changes to `score.py`, run the check, see it fail, and restore: count a repeat join as no slide; give a new chain offset 0 always; compare moves rather than levels for `cause`. Say in your report how many seeds failed for each.

- [ ] **Step 6: Add `test_wobble_keeps_the_true_values_consistent`** over 10 seeds at `timing_wobble=0.15`: each event's true length is within 15% of its planned length, and note order, causes and syllable indices match the plan.

- [ ] **Step 7: Run the whole suite and commit.** `git commit -m "Check the synthesiser's true values on 50 random strings"`

### Task 4: The sung voice

**Files:**
- Create: `hymnstring/synth/voice.py`
- Modify: `hymnstring/synth/__init__.py`
- Test: `tests/synth_probes.py`, `tests/test_synth_voice.py`

**Interfaces:**
- Consumes: `build_score`, `sample_count`, `Score`; `pitch_at`, `truth_of`; `random_hymn`, `random_settings`.
- Produces, in `hymnstring/synth/voice.py`:
  - `sing(score: Score, settings: SynthSettings) -> np.ndarray`: the dry voice, `sample_count` samples of float64 (rules 18 to 21)
  - `write_wav(path: Path, samples: np.ndarray, sample_rate_hz: int) -> None` (rule 27)
  - `MAX_HARMONICS = 30`, `RAMP_S = 0.01`, `DIP_S = 0.015`, `DIP_DEPTH = 0.9`, `FORMANTS`
- Produces, in `hymnstring/synth/__init__.py`:
  - `Synthesis(samples: np.ndarray, sample_rate_hz: int, truth: GroundTruth)`, a frozen dataclass
  - `synthesise(string: HymnString, settings: SynthSettings) -> Synthesis`. In this task it returns the dry voice; Task 5 adds the room.
- Produces, in `tests/synth_probes.py` (shares nothing with the synthesiser, imports only numpy):
  - `measure_f0(samples, rate, at_s, window_s=0.05) -> float`: normalised autocorrelation over the window, lags for 60 to 1200 Hz, taking the smallest lag whose value is at least 0.9 of the maximum, refined by parabolic interpolation. If that picks a formant rather than the pitch, tune the threshold and say so in your report
  - `level_db(samples, rate, start_s, end_s) -> float`: RMS in dB
  - `band_db(samples, rate, low_hz, high_hz) -> float`: energy in a band, in dB, from `rfft`

- [ ] **Step 1: Write failing tests** in `tests/test_synth_voice.py`, each with literal settings:

| Test | Setup | Asserts |
| --- | --- | --- |
| `test_a_pause_is_exactly_silent` | `a:2 .2 2`, 0.5 s | every sample from 1.0 to 2.0 s is `0.0` |
| `test_the_voice_starts_on_silence` | `a:2`, 0.5 s | `samples[0] == 0.0`, and the last sample is under 2% of the peak |
| `test_a_plain_note_has_its_pitch` | `a:2`, `base_hz=130` | `measure_f0` at 0.5 s within 2 cents of 130 |
| `test_a_level_is_the_step_above` | `a:2 ^ 2`, 0.5 s, 200 cents, `base_hz=130` | at 0.5 s within 3 cents of 130, at 1.5 s within 3 cents of `130 * 2 ** (200 / 1200)` |
| `test_a_slide_passes_through_its_middle` | `a:4 ^ 4`, 0.5 s, 1200 cents, `slope_s=0.4` | at 1.8 s within 40 cents of `base_hz * 2 ** 0.5` |
| `test_vibrato_has_its_rate_and_width` | `a:~8`, 0.5 s, rate 5, width 100 | measured every 10 ms from 0.5 to 3.5 s: rate within 0.2 Hz of 5, peak to peak within 15 cents of 100 |
| `test_a_resung_note_dips` | `a:4 4`, 0.5 s | `level_db` over 1.995 to 2.005 s at least 6 dB below 0.995 to 1.005 s |
| `test_a_new_syllable_on_one_level_dips` | `a:4 b:4`, 0.5 s | as above |
| `test_a_pitch_change_within_a_syllable_does_not_dip` | `a:4 !^ 4`, 0.5 s | the same two windows: at most 3 dB below. A louder bead is fine, since the new pitch sits differently on the vowel shape |
| `test_a_dip_fits_between_short_notes` | `>1{a:* * * *}`, 0.2 s | no error; every note centre is louder than the note starts next to it |
| `test_harmonics_stop_below_half_the_sample_rate` | `a:2`, `base_hz=3000`, 16 kHz | `band_db` from 6800 to 7200 Hz at least 40 dB below `band_db` from 2800 to 3200 Hz: the 9 kHz harmonic must not fold back to 7 kHz |
| `test_the_voice_is_shaped_like_a_vowel` | `a:8`, `base_hz=130` | `band_db` from 600 to 900 Hz at least 10 dB above 1400 to 1900 Hz |
| `test_the_same_settings_give_the_same_samples` | demo | `np.array_equal` of two runs |
| `test_a_wav_round_trips` | demo, `tmp_path` | stdlib `wave` reads mono, 2 bytes, rate 16000, the right frame count, and the largest absolute sample is `round(0.9 * 32767)`. Writing again gives identical bytes |

- [ ] **Step 2: Run them to see them fail, then implement `voice.py`, `Synthesis` and `synthesise`.**

- [ ] **Step 3: Write the checks that the audio carries the true values,** parametrised over `range(50)`, using `random_hymn`, `random_settings` and `synthesise`, so that truth and audio come from one run:

  - `test_the_audio_carries_the_true_pitch`: at the centre of every plain note (kind `note` or `fast`, at least 80 ms long, and with no slide within 40 ms of the centre), `measure_f0` is within 15 cents of the true frame nearest that time. At least 98% of notes in the hymn pass, and the test states the count it checked.
  - `test_every_true_breath_is_silent_in_the_audio`: every sample inside each true breath is `0.0`.
  - `test_every_voiced_frame_sounds`: for each voiced frame at least 20 ms from a note boundary, `level_db` over a 10 ms window is above -60 dB relative to the peak.
  - `test_every_true_resung_note_has_a_dip`: for each `resung` note that directly follows another note (no rest), with both at least 120 ms long, the 10 ms around its start is at least 6 dB below the 10 ms at its centre. A re-sung note after a rest has no dip (rule 21): the fade-in is its onset.

- [ ] **Step 4: Run the whole suite, and report its time.** If it passes 60 s, make the measuring cheaper. Commit. `git commit -m "Sing the score: harmonics, vowel shape and re-sung dips"`

### Task 5: Noise, echo and cymbals

**Files:**
- Create: `hymnstring/synth/room.py`
- Modify: `hymnstring/synth/__init__.py`
- Test: `tests/test_synth_room.py`

**Interfaces:**
- Consumes: `sing`, `Score`, `sample_count`, `CYMBALS`, `ECHO`, `NOISE`, `synthesise`; `measure_f0`, `level_db`, `band_db`; `random_hymn`, `random_settings`.
- Produces, in `hymnstring/synth/room.py`:
  - `echo_response(settings: SynthSettings) -> np.ndarray` (rule 25)
  - `in_the_room(voice: np.ndarray, score: Score, settings: SynthSettings) -> np.ndarray`: the finished mix, rule 23's order
  - `CYMBAL_HIT_S = 0.4`
- `synthesise` now returns `in_the_room(sing(...), ...)`.

- [ ] **Step 1: Write failing tests** in `tests/test_synth_room.py`:

| Test | Setup | Asserts |
| --- | --- | --- |
| `test_no_room_settings_leave_the_voice_alone` | demo | `synthesise(...)` samples equal `sing(...)` exactly |
| `test_noise_has_its_exact_level` | demo, `noise_snr_db=20` | with `diff = noisy - clean`, `20 * log10(voice_rms / rms(diff))` is 20 within `1e-6` |
| `test_noise_leaves_the_voice_untouched` | demo, noise on and off, one seed | `diff` is white: `band_db` from 500 to 1000 Hz within 3 dB of 3000 to 3500 Hz, even though the voice isn't |
| `test_noise_fills_the_pauses` | `a:2 .2 2`, noise on | `level_db` from 1.2 to 1.8 s is finite and within 1 dB of the noise's RMS |
| `test_a_seed_changes_the_noise` | two seeds | samples differ |
| `test_echo_adds_its_tail` | demo, `echo_rt60_s=1.0` | length is `11 * 16000 + 16000`, and the samples after 11 s aren't all zero |
| `test_echo_decays_at_its_reverberation_time` | `a:2`, `echo_rt60_s=1.0` | log energy in 50 ms blocks from 0.1 to 0.6 s after the note falls at a rate giving an RT60 within 20% of 1.0 s |
| `test_echo_response_has_its_wet_energy` | `echo_wet_db=-6`, rate 16 kHz | `echo_response` has 16,000 samples at `rt60=1.0`, `[0] == 1`, and `sum(r[1:] ** 2)` within 1e-9 of `10 ** (-6 / 10)` |
| `test_the_direct_voice_survives_the_echo` | demo, `echo_wet_db=-12` | correlation with the dry voice above 0.9 |
| `test_cymbals_hit_on_their_grid` | `a:8`, 0.5 s, `cymbal_every=2` | `cymbal_db=12`: `band_db` above 5 kHz over 30 ms after each of 0, 1, 2 and 3 s is at least 10 dB above the same band over 30 ms ending 0.05 s before the next hit |
| `test_each_section_has_its_own_cymbal_grid` | two sections at 0.5 s and 0.25 s | hits fall at each section's own spacing, from its start |
| `test_cymbals_ignore_timing_wobble` | `timing_wobble=0.15` | first section's hits land on `k * cymbal_every * half_note_s` |
| `test_a_cymbal_peak_has_its_level` | `a:8`, `cymbal_db=6` | largest absolute `cymbal-only` sample (`with - without`) is `voice_rms * 10 ** (6 / 20)` within 1% |
| `test_cymbals_ring_in_the_room` | `cymbals + echo`, hit near the end | energy above 5 kHz after the last note exceeds the same with cymbals off by 10 dB |
| `test_one_source_does_not_disturb_another` | demo | `(cymbals + noise) - cymbals` equals `noise - clean` exactly (within `1e-9`) |
| `test_the_room_does_not_change_the_answers` | demo, everything on | note starts, breaths, syllable times and step size equal the clean run's |
| `test_the_same_seed_gives_identical_bytes` | demo, everything on, `tmp_path` | two `write_wav` outputs are byte-identical |

- [ ] **Step 2: Run them to see them fail, then implement `room.py`** and wire it into `synthesise`.

- [ ] **Step 3: Add `test_wobble_and_drift_reach_the_audio`,** parametrised over 5 seeds: `timing_wobble=0.15` and `drift_cents_per_min=60`, the same pitch check as Task 4's at plain note centres. The truth moved, and the audio must have moved with it.

- [ ] **Step 4: Run the whole suite and commit.** `git commit -m "Add noise, room echo and cymbals to the synthesiser"`

### Task 6: The command-line node

**Files:**
- Create: `hymnstring/synth/__main__.py`
- Modify: `hymnstring/synth/__init__.py`
- Test: `tests/test_synth_node.py`

**Interfaces:**
- Consumes: `synthesise`, `write_wav`, `SynthError`; `SynthInput`, `SynthOutput`, `Voice`; `ContractError`, `Node`, `cli` from `hymnstring/harness.py`.
- Produces: `NODE = Node("synth", SynthInput, SynthOutput, run)` in `hymnstring/synth/__init__.py`, and `python -m hymnstring.synth --in job.json --out truth.json`.

`run` synthesises, creates the parent folder of `out_path`, and writes the WAV. It catches `SynthError` and `OSError` and raises `ContractError` from them, naming `out_path` for a write failure, as `hymnstring/nodes/render/__init__.py` does. It returns `SynthOutput`, whose `voice` has `path=out_path`, the sample rate, `duration_s = len(samples) / rate`, `backend="bypass"` and `accompaniment_path=None`, because with separation bypassed the file is what the next nodes listen to.

- [ ] **Step 1: Write failing tests** in `tests/test_synth_node.py`, using `subprocess` as in `tests/test_render_node.py`, with payloads built from `fixtures/contracts/synth_input.json`:

| Test | Setup | Asserts |
| --- | --- | --- |
| `test_the_node_writes_a_recording_and_returns_the_true_values` | `out_path` in a folder that doesn't exist yet | exit 0; stdout validates as `SynthOutput`; the WAV exists with the frame count `voice.duration_s` implies; `truth.note_starts` has 13 notes; the file's sample rate is `voice.sample_rate_hz` |
| `test_two_runs_write_identical_bytes` | one seed, noise on | identical files |
| `test_bad_input_is_exit_2` | `{"unexpected": 1}` | exit 2, nothing on stdout |
| `test_an_absurd_length_is_exit_2_and_quick` | notation `a:999999999`, `timeout=20` | exit 2, `"Traceback"` not in stderr, stderr names 1800 |
| `test_a_string_with_no_first_syllable_is_exit_2` | notation `2` | exit 2, stderr mentions `syllable` |
| `test_an_unwritable_out_path_is_exit_2` | `out_path` is an existing folder | exit 2, no traceback, stderr names the path |
| `test_a_section_past_the_end_is_exit_2` | `first_phrase` beyond the hymn | exit 2 |

- [ ] **Step 2: Run them to see them fail, then implement `run`, `NODE` and `__main__.py`.**

- [ ] **Step 3: Run the whole suite, and report the count and the time. Run `git status` and confirm no `.wav` is tracked or untracked in the repo.** Commit. `git commit -m "Run the synthesiser from the command line"`
