"""The room around the voice: noise, echo and cymbals, heard through the ears in synth_probes.py.

Rule numbers are those in docs/superpowers/plans/2026-11-02-synthesiser.md.
"""

import functools
import math
import tracemalloc
from types import SimpleNamespace

import numpy as np
import pytest
from synth_probes import band_db, largest_prime_factor, level_db, plain_note_errors

from hymnstring.contracts import HymnString, SynthSettings
from hymnstring.contracts.synth import SynthSection
from hymnstring.notation import parse_hymn
from hymnstring.synth import (
    CYMBAL_HIT_S,
    build_score,
    echo_response,
    in_the_room,
    random_hymn,
    random_settings,
    sample_count,
    sing,
    synthesise,
    true_values,
    write_wav,
)

DEMO = "#1[A:2 ^ 1 v 1] ^ lē:~2 .2 v (lou:1)x3^ >1{i:*} a:2 !v2 #1[(a):2 ^ 1 v 1] v 4"  # 11 s at 0.5 s
LONG = "a:~24 ^ 24 b:24 .8 24 ^ 28"  # 132 half-note units, 66 s at 0.5 s
RATE = 16000
HIT = 6400  # samples in a cymbal hit: 0.4 s at 16 kHz


def settings(half_note_s=0.5, step_cents=200.0, seed=1, **more):
    return SynthSettings(
        seed=seed,
        sections=(SynthSection(first_phrase=0, half_note_s=half_note_s, step_cents=step_cents),),
        **more,
    )


def two_sections(**more):
    """0.5 s a half note for phrase 1, then 0.25 s from phrase 2 on."""
    return SynthSettings(
        seed=1,
        sections=(
            SynthSection(first_phrase=0, half_note_s=0.5, step_cents=200.0),
            SynthSection(first_phrase=1, half_note_s=0.25, step_cents=200.0),
        ),
        **more,
    )


def string_of(*notations):
    """The HymnString whose phrases p1, p2, ... have these notations."""
    phrases = [
        {"phrase_id": f"p{number}", "direction": "ltr", "notation": notation}
        for number, notation in enumerate(notations, 1)
    ]
    return HymnString.model_validate({"format_version": 1, "phrases": phrases})


def sung(notation, **more):
    """The samples of one phrase sung with these settings."""
    return synthesise(string_of(notation), settings(**more)).samples


@functools.cache
def demo(**more):
    """The samples of the demo phrase with these settings. Cached, so never change what it returns."""
    return sung(DEMO, **more)


def voice_rms(samples):
    """The RMS of the non-zero samples: the level the room sets everything against."""
    return math.sqrt(float(np.mean(samples[samples != 0] ** 2)))


def snr_db(voice, noise):
    """How far the voice's level lies above the noise's RMS, in dB. Silent noise is +inf."""
    return 20 * math.log10(voice_rms(voice)) - level_db(noise, RATE, 0, len(noise) / RATE)


def high_db(samples, start_s, end_s):
    """The energy above 5 kHz between two times, in dB: the voice has next to none, the cymbals a lot."""
    return band_db(samples[round(start_s * RATE) : round(end_s * RATE)], RATE, 5000, 8000)


def cymbals_alone(string, cfg):
    """Only the cymbals: the mix, minus the same mix without them. Exactly 0.0 wherever no hit sounds."""
    bare = cfg.model_copy(update={"cymbal_every": None})
    return synthesise(string, cfg).samples - synthesise(string, bare).samples


def runs(track):
    """The (first, end) sample numbers of each stretch of non-zero samples."""
    edges = np.flatnonzero(np.diff((track != 0).astype(int), prepend=0, append=0))
    return list(zip(edges[::2].tolist(), edges[1::2].tolist()))


# -- nothing asked for, nothing added


def test_no_room_settings_leave_the_voice_alone():
    cfg = settings()
    score = build_score(parse_hymn(f"p1 ltr: {DEMO}"), cfg)

    assert np.array_equal(demo(), sing(score, cfg))


def test_the_room_leaves_the_dry_voice_alone():
    cfg = settings()
    score = build_score(parse_hymn(f"p1 ltr: {DEMO}"), cfg)
    dry = sing(score, cfg)
    kept = dry.copy()

    mix = in_the_room(dry, score, cfg)
    assert np.array_equal(mix, dry) and not np.shares_memory(mix, dry)  # a copy, even when nothing is added

    everything = settings(noise_snr_db=10.0, echo_rt60_s=1.0, cymbal_every=2)
    in_the_room(dry, score, everything)
    assert np.array_equal(dry, kept)


@pytest.mark.filterwarnings("error")
def test_a_voice_that_never_sounds_stays_silent_in_every_room():
    # every level is relative to the voice's, and a voice that never sounds has none: no NaN, no warning
    cfg = settings(noise_snr_db=10.0, echo_rt60_s=0.5, cymbal_every=1, cymbal_db=6.0)
    score = build_score(parse_hymn("p1 ltr: a:2"), cfg)

    mix = in_the_room(np.zeros(sample_count(score, cfg)), score, cfg)

    assert len(mix) == 1 * RATE + RATE // 2
    assert np.all(mix == 0.0)


# -- noise (rule 26)


@pytest.mark.parametrize(
    "others",
    [{}, {"echo_rt60_s": 1.0, "cymbal_every": 2, "cymbal_db": 6.0}],
    ids=["alone", "after the echo and cymbals"],
)
def test_noise_has_its_exact_level(others):
    # the level is set against the dry voice's, and the noise comes last, so the echo never touches it
    diff = demo(noise_snr_db=20.0, **others) - demo(**others)

    assert abs(snr_db(demo(), diff) - 20) < 1e-6


def test_noise_leaves_the_voice_untouched():
    clean = demo()
    diff = demo(noise_snr_db=10.0) - clean

    assert abs(band_db(diff, RATE, 500, 1000) - band_db(diff, RATE, 3000, 3500)) <= 3
    # the voice is nowhere near white, so the noise being so means it is not shaped by the voice
    assert band_db(clean, RATE, 500, 1000) - band_db(clean, RATE, 3000, 3500) >= 20


def test_noise_fills_the_pauses():
    quiet, noisy = sung("a:2 .2 2"), sung("a:2 .2 2", noise_snr_db=20.0)
    noise_db = 20 * math.log10(voice_rms(quiet)) - 20

    assert np.all(quiet[1 * RATE : 2 * RATE] == 0.0)  # the pause is silent without it
    level = level_db(noisy, RATE, 1.2, 1.8)
    assert math.isfinite(level) and abs(level - noise_db) <= 1


def test_a_seed_changes_the_noise():
    assert not np.array_equal(demo(noise_snr_db=20.0, seed=1), demo(noise_snr_db=20.0, seed=2))


# -- echo (rule 25)


def test_echo_adds_its_tail():
    samples = demo(echo_rt60_s=1.0)

    assert len(samples) == 11 * RATE + RATE
    assert np.any(samples[11 * RATE :] != 0.0)


def test_echo_decays_at_its_reverberation_time():
    samples = sung("a:2", echo_rt60_s=1.0)  # the note ends at 1 s, and the room rings on after it

    starts = 1.0 + 0.1 + 0.05 * np.arange(10)  # ten blocks of 50 ms, from 0.1 to 0.6 s after the note
    energies = np.array([np.sum(samples[round(s * RATE) : round((s + 0.05) * RATE)] ** 2) for s in starts])
    assert np.all(energies > 0), "the room is silent after the note"
    rate_db_per_s = np.polyfit(starts + 0.025, 10 * np.log10(energies), 1)[0]

    assert 0.8 <= -60 / rate_db_per_s <= 1.2  # the time to fall 60 dB


def test_echo_response_has_its_wet_energy():
    response = echo_response(settings(echo_rt60_s=1.0, echo_wet_db=-6.0))

    assert len(response) == 16000
    assert response[0] == 1
    assert abs(np.sum(response[1:] ** 2) - 10 ** (-6 / 10)) <= 1e-9


@pytest.mark.parametrize(
    "rt60, rate, count",
    [(0.1234, 16000, 1975), (2.5, 44100, 110250), (1.1, 16000, 17601), (0.3, 8000, 2400)],
)
def test_the_echo_response_is_as_long_as_the_tail(rt60, rate, count):
    # 0.1234 * 16000 is 1974.4. And 1.1 is a hair over 1.1, so its 17,600 samples need one more: counted
    # in floats the product is exactly 17600.0, so only an exact count agrees with sample_count.
    cfg = settings(echo_rt60_s=rt60, sample_rate_hz=rate)
    score = build_score(parse_hymn("p1 ltr: a:2"), cfg)  # 1 s

    assert len(echo_response(cfg)) == count
    assert sample_count(score, cfg) == rate + count


@pytest.mark.filterwarnings("error")
def test_a_very_short_reverberation_adds_nothing_but_a_sample():
    wet = demo(echo_rt60_s=1e-6)  # one sample long: the response is just the direct sound

    assert len(wet) == len(demo()) + 1
    assert np.max(np.abs(wet - np.append(demo(), 0.0))) <= 1e-12  # the FFT leaves rounding, not an echo


def test_the_direct_voice_survives_the_echo():
    cfg = settings(echo_rt60_s=1.0, echo_wet_db=-12.0)
    score = build_score(parse_hymn(f"p1 ltr: {DEMO}"), cfg)
    dry, wet = sing(score, cfg), synthesise(string_of(DEMO), cfg).samples

    assert np.corrcoef(dry, wet)[0, 1] > 0.9


def test_the_echo_does_not_wrap_round_to_the_start():
    # A voice still sounding when the recording ends, so that its echo runs on past the end: the tail
    # is shorter than the response. Wrapped round, that echo would land on the start, which must stay
    # silent until the voice sounds, and the whole mix must be the plain convolution cut to length.
    cfg = settings(echo_rt60_s=0.5, sample_rate_hz=8000)
    score = build_score(parse_hymn("p1 ltr: a:2"), cfg)
    n = sample_count(score, cfg)
    voice = np.zeros(n)
    voice[-200:] = np.random.default_rng(0).standard_normal(200)
    response = echo_response(cfg)

    mix = in_the_room(voice, score, cfg)

    assert (n, len(response)) == (12000, 4000)
    assert np.max(np.abs(mix[: n - 200])) <= 1e-9
    assert np.max(np.abs(mix - np.convolve(voice, response)[:n])) <= 1e-9


# -- cymbals (rule 24)


def test_cymbals_hit_on_their_grid():
    samples = sung("a:8", cymbal_every=2, cymbal_db=12.0)  # 4 s, with a hit every 1 s

    for hit in range(4):
        ring = high_db(samples, hit, hit + 0.03)  # the 30 ms after the hit
        calm = high_db(samples, hit + 1 - 0.08, hit + 1 - 0.05)  # 30 ms ending 0.05 s before the next
        assert ring - calm >= 10, f"the hit at {hit} s is only {ring - calm:.1f} dB above the quiet before"


def test_each_section_has_its_own_cymbal_grid():
    # phrase 1 lasts 2 s with a hit every 1 s; phrase 2 lasts 2 s with a hit every 0.5 s, the first on
    # its start. The hits that would fall on 2 s and 4 s, at the ends of the sections, are not made.
    string, cfg = string_of("a:4", "= 8"), two_sections(cymbal_every=2)
    track = cymbals_alone(string, cfg)

    assert runs(track) == [(start, start + HIT) for start in (0, 16000, 32000, 40000, 48000, 56000)]
    # no two hits overlap, so none is louder than a single hit's peak, which at 0 dB is the voice's RMS:
    # a second hit at 2 s, from the end of phrase 1, would sit on the first and add to it
    dry = synthesise(string, cfg.model_copy(update={"cymbal_every": None})).samples
    assert np.max(np.abs(track)) == pytest.approx(voice_rms(dry), rel=1e-9)


def test_cymbals_ignore_timing_wobble():
    string, cfg = string_of("a:2 2 2 2 2 2"), settings(timing_wobble=0.15, cymbal_every=2)  # 1 s notes
    truth = synthesise(string, cfg).truth
    end = truth.pulse_unit.sections[0].end_s

    assert any(abs(note.start_s - i) > 0.05 for i, note in enumerate(truth.note_starts.notes))  # it moved
    hits = [first for first, _ in runs(cymbals_alone(string, cfg))]
    assert hits == [k * RATE for k in range(math.ceil(end))]  # every 1 s, while that is before the end


def test_a_cymbal_peak_has_its_level():
    track = cymbals_alone(string_of("a:8"), settings(cymbal_every=2, cymbal_db=6.0))

    assert np.max(np.abs(track)) == pytest.approx(voice_rms(sung("a:8")) * 10 ** (6 / 20), rel=0.01)


def test_a_cymbal_hit_is_bright_noise_that_dies_away():
    hit = cymbals_alone(string_of("a:8"), settings(cymbal_every=100))  # the next hit is 50 s away

    assert CYMBAL_HIT_S == 0.4 and runs(hit) == [(0, HIT)]
    first, second = (np.sum(hit[lo : lo + 1280] ** 2) for lo in (0, 1280))  # 80 ms each
    assert 7.2 <= 10 * math.log10(first / second) <= 10.2  # e ** -(t / 0.08) in amplitude: 8.7 dB
    assert band_db(hit, RATE, 5000, 8000) >= band_db(hit, RATE, 100, 1100) + 15  # white would be 4.8 dB


def test_cymbals_ring_in_the_room():
    # the last hit is at 1 s and is over by 1.4 s, before the note ends at 1.5 s: only the room is left
    cymbals = sung("a:3", cymbal_every=2, cymbal_db=24.0, echo_rt60_s=1.0)
    bare = sung("a:3", echo_rt60_s=1.0)
    after = round(1.5 * RATE)

    ring, calm = band_db(cymbals[after:], RATE, 5000, 8000), band_db(bare[after:], RATE, 5000, 8000)
    assert ring - calm >= 10  # a difference, so that silence on both sides (-inf and -inf) fails


# -- the mix (rules 22 and 23)


def test_one_source_does_not_disturb_another():
    cymbals, noise = {"cymbal_every": 2, "cymbal_db": 6.0}, {"noise_snr_db": 15.0}
    noise_only = demo(**noise) - demo()

    assert np.any(noise_only != 0.0)
    assert np.max(np.abs((demo(**cymbals, **noise) - demo(**cymbals)) - noise_only)) <= 1e-9


def test_the_room_does_not_change_the_answers():
    string = string_of(DEMO)
    clean = synthesise(string, settings()).truth
    roomy = synthesise(
        string, settings(noise_snr_db=20.0, echo_rt60_s=1.0, cymbal_every=2, cymbal_db=6.0)
    ).truth

    assert roomy.note_starts == clean.note_starts  # the notes and the breaths
    assert roomy.syllable_times == clean.syllable_times
    assert roomy.step_size == clean.step_size


def test_the_same_seed_gives_identical_bytes(tmp_path):
    string = string_of(DEMO)
    cfg = settings(noise_snr_db=20.0, echo_rt60_s=1.0, cymbal_every=2, cymbal_db=6.0)
    syntheses = [synthesise(string, cfg) for _ in range(2)]
    written = []
    for number, synthesis in enumerate(syntheses):
        write_wav(tmp_path / f"demo{number}.wav", synthesis.samples, synthesis.sample_rate_hz)
        written.append((tmp_path / f"demo{number}.wav").read_bytes())

    assert np.array_equal(syntheses[0].samples, syntheses[1].samples)
    assert written[0] == written[1]


# -- memory: the room is built in one buffer, and its FFT is padded (rule 25)


@functools.cache
def awkward_room():
    """LONG with timing wobble, which gives it a sample count with a large prime factor, in a room with
    every source on and the longest echo; and its dry voice, made once."""
    cfg = settings(timing_wobble=0.1, echo_rt60_s=10.0, cymbal_every=2, cymbal_db=6.0, noise_snr_db=20.0)
    score = build_score(parse_hymn(f"p1 ltr: {LONG}"), cfg)
    assert largest_prime_factor(sample_count(score, cfg)) > 1000
    return score, cfg, sing(score, cfg)


def test_the_room_needs_at_most_eight_arrays_of_memory():
    score, cfg, dry = awkward_room()  # the voice is made before tracing: it is the room that is measured
    n = len(dry)

    tracemalloc.start()  # it sees numpy's buffers
    try:
        mix = in_the_room(dry, score, cfg)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()

    assert len(mix) == n
    assert peak <= 8 * n * 8, f"{peak / (n * 8):.1f} arrays of {n} doubles"


def test_the_echo_fft_is_long_enough_and_has_small_factors(monkeypatch):
    # tracemalloc can't see what an awkward length makes the transform allocate, so look at the length
    score, cfg, dry = awkward_room()
    whole = len(dry) + len(echo_response(cfg)) - 1  # what the linear convolution of the two needs
    lengths, real_rfft, real_irfft = [], np.fft.rfft, np.fft.irfft

    def spy_rfft(a, n=None, *more, **named):
        lengths.append(len(a) if n is None else n)
        return real_rfft(a, n, *more, **named)

    def spy_irfft(a, n=None, *more, **named):
        lengths.append(2 * (len(a) - 1) if n is None else n)
        return real_irfft(a, n, *more, **named)

    monkeypatch.setattr(np.fft, "rfft", spy_rfft)
    monkeypatch.setattr(np.fft, "irfft", spy_irfft)
    in_the_room(dry, score, cfg)

    assert len(lengths) == 3 and len(set(lengths)) == 1  # the voice, the response and the way back
    length = lengths[0]
    assert whole <= length <= 1.05 * whole
    assert largest_prime_factor(length) <= 5


# -- the audio carries the wobble and the drift (50 random strings in test_synth_voice.py; 5 here)


@pytest.mark.parametrize("seed", range(5))
def test_wobble_and_drift_reach_the_audio(seed):
    hymn = random_hymn(seed)
    steady = random_settings(seed, len(hymn.string.phrases))
    cfg = steady.model_copy(update={"timing_wobble": 0.15, "drift_cents_per_min": 60.0})
    synthesis = synthesise(hymn.string, cfg)

    errors = plain_note_errors(synthesis, hymn, cfg.slope_s)
    close = sum(error <= 15 for error in errors)  # a pitch that couldn't be measured is NaN, and fails

    assert synthesis.truth.note_starts != true_values(hymn.string, steady).note_starts  # the truth moved
    assert errors, f"seed {seed}: no plain note to check"
    assert close >= 0.98 * len(errors), f"seed {seed}: {close} of {len(errors)} notes within 15 cents"

    # Judged against the truth with the wobble but not the drift, the same notes are off by about the
    # drift (1 cent a second), more than 5 cents by the end of any of these hymns: so the audio has it.
    wobbled = steady.model_copy(update={"timing_wobble": 0.15})
    undrifted = SimpleNamespace(
        samples=synthesis.samples,
        sample_rate_hz=synthesis.sample_rate_hz,
        truth=true_values(hymn.string, wobbled),
    )
    assert max(plain_note_errors(undrifted, hymn, cfg.slope_s)) > 5
