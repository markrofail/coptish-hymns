"""The sung voice, heard through the ears in synth_probes.py, which share nothing with it.

Rule numbers are those in docs/superpowers/plans/2026-11-02-synthesiser.md.
"""

import functools
import math
import tracemalloc
import wave

import numpy as np
import pytest
from synth_probes import (
    band_db,
    cents_above,
    largest_prime_factor,
    level_db,
    measure_f0,
    note_spans,
    plain_note_errors,
)

import hymnstring.synth.voice as voice_module
from hymnstring.contracts import HymnString, SynthSettings
from hymnstring.contracts.synth import SynthSection
from hymnstring.notation import parse_hymn
from hymnstring.synth import (
    build_score,
    random_hymn,
    random_settings,
    sample_count,
    sing,
    synthesise,
    write_wav,
)

DEMO = "#1[A:2 ^ 1 v 1] ^ lē:~2 .2 v (lou:1)x3^ >1{i:*} a:2 !v2 #1[(a):2 ^ 1 v 1] v 4"
LONG = "a:~24 ^ 24 b:24 .8 24 ^ 28"  # 132 half-note units, 66 s at 0.5 s: a vibrato note, a slide, a rest
RATE = 16000


def settings(half_note_s=0.5, step_cents=200.0, **more):
    return SynthSettings(
        seed=1,
        sections=(SynthSection(first_phrase=0, half_note_s=half_note_s, step_cents=step_cents),),
        **more,
    )


def string_of(notation):
    """The HymnString of one phrase."""
    phrase = {"phrase_id": "p1", "direction": "ltr", "notation": notation}
    return HymnString.model_validate({"format_version": 1, "phrases": [phrase]})


def voice(notation, **more):
    """The samples of this notation sung with these settings."""
    return synthesise(string_of(notation), settings(**more)).samples


def level_around(samples, seconds):
    """The level of the 10 ms around a time."""
    return level_db(samples, RATE, seconds - 0.005, seconds + 0.005)


def drop_db(samples, quiet_s, loud_s):
    """How far the 10 ms around one time sits below the 10 ms around another."""
    return level_around(samples, loud_s) - level_around(samples, quiet_s)


# -- silence, the pitch of a note and how it fades (rules 17 to 20)


def test_a_pause_is_exactly_silent():
    samples = voice("a:2 .2 2", half_note_s=0.5)

    assert np.all(samples[1 * RATE : 2 * RATE] == 0.0)
    assert np.any(samples[: 1 * RATE] != 0.0) and np.any(samples[2 * RATE :] != 0.0)  # the notes do sound


def test_the_voice_starts_on_silence():
    samples = voice("a:2", half_note_s=0.5)

    assert samples[0] == 0.0
    assert abs(samples[-1]) < 0.02 * np.max(np.abs(samples))


def test_a_run_fades_in_and_out_over_10_ms():
    # at 1000 Hz one millisecond is whole periods, so a level there doesn't depend on phase
    samples = voice("a:2", half_note_s=0.5, base_hz=1000.0)  # sounding from 0 to 1 s

    steady = level_db(samples, RATE, 0.5, 0.501)
    for ms, share in [(2.5, 0.25), (5.0, 0.5), (7.5, 0.75), (12.0, 1.0)]:  # a straight line up to 10 ms
        want = 20 * math.log10(share)
        fade_in = level_db(samples, RATE, (ms - 0.5) / 1000, (ms + 0.5) / 1000)
        fade_out = level_db(samples, RATE, 1 - (ms + 0.5) / 1000, 1 - (ms - 0.5) / 1000)
        assert abs(fade_in - steady - want) <= 1 and abs(fade_out - steady - want) <= 1


def test_a_note_shorter_than_20_ms_fades_over_half_its_length():
    blip = voice("a:1", half_note_s=0.01, base_hz=1000.0)  # 5 ms up and 5 ms down, so it still peaks
    held = voice("a:2", half_note_s=0.5, base_hz=1000.0)

    assert np.max(np.abs(blip)) >= 0.8 * np.max(np.abs(held))


def test_the_dry_voice_leaves_the_echo_tail_silent():
    cfg = settings(half_note_s=0.5, echo_rt60_s=0.5)
    samples = sing(build_score(parse_hymn("p1 ltr: a:2"), cfg), cfg)

    assert len(samples) == 16000 + 8000  # the note, then 0.5 s of room for the echo
    assert np.all(samples[16000:] == 0.0)


def test_a_plain_note_has_its_pitch():
    samples = voice("a:2", half_note_s=0.5, base_hz=130.0)

    assert abs(cents_above(measure_f0(samples, RATE, 0.5), 130.0)) <= 2


def test_a_level_is_the_step_above():
    samples = voice("a:2 ^ 2", half_note_s=0.5, step_cents=200.0, base_hz=130.0)

    assert abs(cents_above(measure_f0(samples, RATE, 0.5), 130.0)) <= 3
    assert abs(cents_above(measure_f0(samples, RATE, 1.5), 130 * 2 ** (200 / 1200))) <= 3


def test_a_slide_passes_through_its_middle():
    # the slide takes the last 0.4 s of the first note, 1.6 to 2.0 s, and at 1.8 s is half way up
    samples = voice("a:4 ^ 4", half_note_s=0.5, step_cents=1200.0, slope_s=0.4, base_hz=130.0)

    assert abs(cents_above(measure_f0(samples, RATE, 1.8), 130 * 2**0.5)) <= 40


def test_vibrato_has_its_rate_and_width():
    samples = voice("a:~8", half_note_s=0.5, base_hz=130.0, vibrato_rate_hz=5.0, vibrato_width_cents=100.0)

    seconds = np.arange(50, 351) / 100  # every 10 ms from 0.5 to 3.5 s
    cents = np.array([cents_above(measure_f0(samples, RATE, t), 130.0) for t in seconds])
    middle = (cents.max() + cents.min()) / 2
    up = np.flatnonzero((cents[:-1] < middle) & (cents[1:] >= middle))  # the frame before each rise
    crossings = (up + (middle - cents[up]) / (cents[up + 1] - cents[up])) / 100  # in seconds, from 0.5 s
    rate_hz = (len(crossings) - 1) / (crossings[-1] - crossings[0])  # whole cycles over the time they took

    assert abs(rate_hz - 5.0) <= 0.2
    assert abs((cents.max() - cents.min()) - 100.0) <= 15


# -- the dip that makes a re-sung note audible (rule 21)


def test_a_resung_note_dips():
    samples = voice("a:4 4", half_note_s=0.5)  # the second note starts at 2.0 s

    assert drop_db(samples, quiet_s=2.0, loud_s=1.0) >= 6


def test_a_new_syllable_on_one_level_dips():
    samples = voice("a:4 b:4", half_note_s=0.5)

    assert drop_db(samples, quiet_s=2.0, loud_s=1.0) >= 6


def test_a_pitch_change_within_a_syllable_does_not_dip():
    samples = voice("a:4 !^ 4", half_note_s=0.5, step_cents=200.0)

    # a louder bead is fine, since the new pitch sits differently on the vowel shape
    assert drop_db(samples, quiet_s=2.0, loud_s=1.0) <= 3


def test_a_dip_fits_between_short_notes():
    samples = voice(">1{a:* * * *}", half_note_s=0.2)  # four beads of 50 ms, from 0, 50, 100 and 150 ms

    starts = [0.05, 0.10, 0.15]  # the beads that follow another dip at their start
    for i, centre in enumerate([0.025, 0.075, 0.125, 0.175]):
        for j in (i - 1, i):  # the starts either side of this bead
            if 0 <= j < len(starts):
                assert level_around(samples, centre) > level_around(samples, starts[j])


def test_a_dip_reaches_only_a_third_into_a_note():
    # four beads of 15 ms between longer notes: each dip reaches 5 ms either side of a start, and leaves
    # the middle of its bead alone. At 1000 Hz, 4 ms is whole periods, so a level doesn't depend on phase.
    samples = voice("a:2 >1{b:* * * *} c:2", half_note_s=0.06, base_hz=1000.0)

    steady = level_db(samples, RATE, 0.058, 0.062)  # the middle of the first note, 0 to 120 ms
    for centre in [0.1275, 0.1425, 0.1575, 0.1725]:
        assert level_db(samples, RATE, centre - 0.002, centre + 0.002) >= steady - 1


def test_a_note_after_a_pause_has_no_dip():
    # sung again after a rest, it fades in like the first note, with nothing dipped
    samples = voice("a:2 .2 2", half_note_s=0.5, base_hz=1000.0)

    assert abs(level_around(samples, 2.010) - level_around(samples, 0.010)) <= 1


# -- the shape of the sound (rules 18 and 19)


def test_harmonics_stop_below_half_the_sample_rate():
    samples = voice("a:2", half_note_s=0.5, base_hz=3000.0, sample_rate_hz=16000)

    # the 3rd harmonic is 9 kHz, which would fold back to 7 kHz
    assert band_db(samples, RATE, 6800, 7200) <= band_db(samples, RATE, 2800, 3200) - 40


def test_the_voice_has_thirty_harmonics():
    samples = voice("a:8", half_note_s=0.5, base_hz=130.0)

    # the 30th harmonic is at 3900 Hz, and a 31st would be at 4030 Hz
    assert band_db(samples, RATE, 3860, 3940) >= band_db(samples, RATE, 3990, 4070) + 40


def test_the_voice_is_shaped_like_a_vowel():
    samples = voice("a:8", half_note_s=0.5, base_hz=130.0)

    assert band_db(samples, RATE, 600, 900) >= band_db(samples, RATE, 1400, 1900) + 10


# -- the same every time, and on disk (rule 27)


def test_the_same_settings_give_the_same_samples():
    assert np.array_equal(voice(DEMO), voice(DEMO))


def test_a_wav_round_trips(tmp_path):
    synthesis = synthesise(string_of(DEMO), settings())
    path = tmp_path / "demo.wav"
    write_wav(path, synthesis.samples, synthesis.sample_rate_hz)
    written = path.read_bytes()

    with wave.open(str(path), "rb") as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, 16000)
        assert wav.getnframes() == 11 * 16000  # the demo lasts 11 s
        pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
    assert np.abs(pcm.astype(int)).max() == round(0.9 * 32767)

    write_wav(path, synthesis.samples, synthesis.sample_rate_hz)
    assert path.read_bytes() == written


def test_a_silent_wav_is_written_as_silence(tmp_path):
    path = tmp_path / "silence.wav"
    write_wav(path, np.zeros(160), 16000)

    with wave.open(str(path), "rb") as wav:
        assert wav.readframes(wav.getnframes()) == bytes(2 * 160)


# -- memory: the voice is made in blocks, and its FFT is padded (rule 19)


def awkward_score():
    """LONG with timing wobble, which gives it a sample count with a large prime factor: an FFT of that
    exact length is several times bigger and slower than one of a length with only small factors."""
    cfg = settings(half_note_s=0.5, timing_wobble=0.1)
    score = build_score(parse_hymn(f"p1 ltr: {LONG}"), cfg)
    assert largest_prime_factor(sample_count(score, cfg)) > 1000
    return score, cfg


def test_the_voice_needs_at_most_eight_arrays_of_memory():
    score, cfg = awkward_score()
    n = sample_count(score, cfg)

    tracemalloc.start()  # it sees numpy's buffers
    try:
        samples = sing(score, cfg)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()

    assert len(samples) == n
    assert peak <= 8 * n * 8, f"{peak / (n * 8):.1f} arrays of {n} doubles"


def test_the_vowel_fft_is_padded_to_a_length_with_small_factors(monkeypatch):
    # tracemalloc can't see what an awkward length makes the transform allocate, so look at the length
    score, cfg = awkward_score()
    n = sample_count(score, cfg)
    lengths, real_rfft = [], np.fft.rfft

    def spy(a, n=None, *more, **named):
        lengths.append(len(a) if n is None else n)
        return real_rfft(a, n, *more, **named)

    monkeypatch.setattr(np.fft, "rfft", spy)
    sing(score, cfg)

    [length] = lengths  # one transform, over the whole signal
    assert n <= length <= 1.05 * n
    assert largest_prime_factor(length) <= 5


def test_blocks_do_not_change_the_samples(monkeypatch):
    # DEMO has a vibrato note, slides, a rest and dips, and blocks of 4096 samples cut across all of them
    monkeypatch.setattr(voice_module, "BLOCK", 2**30)
    whole = voice(DEMO)
    monkeypatch.setattr(voice_module, "BLOCK", 4096)
    blocks = voice(DEMO)

    assert len(whole) == len(blocks) == 11 * 16000
    assert np.max(np.abs(blocks - whole)) <= 1e-9 * np.max(np.abs(whole))


# -- the audio carries the true values (50 random strings)
#
# `sung` runs each string once, so that its truth and its audio come from one run. The helpers read
# what the audio holds at the places the true values name. They never use the score: the plan that
# `random_hymn` wrote beside the string says which notes are plain.


@functools.cache
def planned(seed):
    """The random string of this seed, with its plan and its settings."""
    hymn = random_hymn(seed)
    return hymn, random_settings(seed, len(hymn.string.phrases))


@functools.cache
def sung(seed):
    """The synthesis of the random string of this seed."""
    hymn, cfg = planned(seed)
    synthesis = synthesise(hymn.string, cfg)
    assert synthesis.sample_rate_hz == RATE  # the helpers below listen at this rate
    return synthesis


def voiced_levels(synthesis):
    """The level, in dB below the peak, of the 10 ms around each voiced frame that is at least 20 ms
    from a note boundary."""
    truth, samples = synthesis.truth, synthesis.samples
    track = truth.pitch_track
    starts = {n.start_s for n in truth.note_starts.notes} | {b.start_s for b in truth.note_starts.breaths}
    edges = np.array(sorted(starts | {truth.pulse_unit.sections[-1].end_s}))
    frames = np.arange(len(track.f0_hz)) * track.hop_s
    voiced = np.array([hz is not None for hz in track.f0_hz])
    clear = np.abs(frames[:, None] - edges[None, :]).min(axis=1) >= 0.02
    peak_db = 20 * math.log10(np.max(np.abs(samples)))
    return [level_around(samples, t) - peak_db for t in frames[voiced & clear]]


def resung_drops(synthesis):
    """How far, in dB, the 10 ms around the start of each re-sung note sits below the 10 ms at its
    centre. A note counts if it directly follows another note, and both last at least 120 ms."""
    truth = synthesis.truth
    after_a_rest = {b.end_s for b in truth.note_starts.breaths}
    spans = note_spans(truth)
    drops = []
    for i, note in enumerate(truth.note_starts.notes):
        (before_start, before_end), (start, end) = spans[i - 1], spans[i]
        long_enough = min(before_end - before_start, end - start) >= 0.12
        if note.cause == "resung" and start not in after_a_rest and long_enough:
            drops.append(drop_db(synthesis.samples, quiet_s=start, loud_s=(start + end) / 2))
    return drops


@pytest.mark.parametrize("seed", range(50))
def test_the_audio_carries_the_true_pitch(seed):
    hymn, cfg = planned(seed)
    errors = plain_note_errors(sung(seed), hymn, cfg.slope_s)
    close = sum(error <= 15 for error in errors)  # a pitch that couldn't be measured is NaN, and fails

    assert errors, f"seed {seed}: no plain note to check"
    assert close >= 0.98 * len(errors), f"seed {seed}: {close} of {len(errors)} notes within 15 cents"


@pytest.mark.parametrize("seed", range(50))
def test_every_true_breath_is_silent_in_the_audio(seed):
    synthesis = sung(seed)
    seconds = np.arange(len(synthesis.samples)) / synthesis.sample_rate_hz
    for breath in synthesis.truth.note_starts.breaths:
        inside = (seconds >= breath.start_s) & (seconds < breath.end_s)
        assert inside.any() and np.all(synthesis.samples[inside] == 0.0), f"seed {seed}: a breath sounds"


@pytest.mark.parametrize("seed", range(50))
def test_every_voiced_frame_sounds(seed):
    levels = voiced_levels(sung(seed))

    assert levels, f"seed {seed}: no voiced frame to check"
    assert min(levels) > -60, f"seed {seed}: {sum(db <= -60 for db in levels)} of {len(levels)} too quiet"


@pytest.mark.parametrize("seed", range(50))
def test_every_true_resung_note_has_a_dip(seed):
    drops = resung_drops(sung(seed))

    assert min(drops, default=6) >= 6, f"seed {seed}: {sum(d < 6 for d in drops)} of {len(drops)} shallow"
