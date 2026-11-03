"""Puts the voice in a room: cymbals, then echo, then noise (rule 23).

Every level is set against the RMS of the dry voice, so that no source changes the level of another,
and each source draws from a generator of its own (rule 22), so that turning one on never changes what
another does. The echo is a linear convolution: its FFT is as long as the whole result, so the echo of
the end can't wrap round onto the start. The mix is built in one buffer that goes as soon as its
spectrum is taken, and spectra are multiplied in place, so that a long hymn doesn't ask for many times
its own size in memory. Rule numbers are those in docs/superpowers/plans/2026-11-02-synthesiser.md.
"""

import math
from fractions import Fraction

import numpy as np

from hymnstring.contracts import SynthSettings
from hymnstring.synth.fft import fast_length
from hymnstring.synth.score import CYMBALS, ECHO, NOISE, Score

CYMBAL_HIT_S = 0.4  # a hit lasts this long
CYMBAL_FALL_S = 0.08  # and falls by a factor of e over this long


def echo_response(settings: SynthSettings) -> np.ndarray:
    """Rule 25: 1 at time 0, then white noise that falls 60 dB over the reverberation time, scaled to
    the wet energy. It has as many samples as the tail that rule 17 adds to the recording."""
    rate, rt60 = settings.sample_rate_hz, settings.echo_rt60_s
    count = math.ceil(Fraction(rt60) * rate)
    rng = np.random.default_rng([settings.seed, ECHO])
    seconds = np.arange(1, count) / rate
    tail = rng.standard_normal(count - 1) * 10 ** (-3 * seconds / rt60)
    energy = np.sum(tail**2)
    if energy > 0:  # a response of one sample has no tail to scale
        tail *= math.sqrt(10 ** (settings.echo_wet_db / 10) / energy)
    return np.concatenate(([1.0], tail))


def in_the_room(voice: np.ndarray, score: Score, settings: SynthSettings) -> np.ndarray:
    """Rule 23: the voice and cymbals, then the echo, then the noise. The voice has as many samples as
    `sample_count`; it is left alone, and the mix is a new array of the same length."""
    level = _sounding_rms(voice)
    if settings.echo_rt60_s is None:
        mix = _voice_and_cymbals(voice, score, settings, level, len(voice))
    else:
        mix = _echoed(voice, score, settings, level)
    if settings.noise_snr_db is not None:
        _add_noise(mix, settings, level)
    return mix


def _sounding_rms(voice: np.ndarray) -> float:
    """The RMS of the voice's non-zero samples, or 0.0 if it never sounds. A dot product makes no array
    of its own."""
    sounding = np.count_nonzero(voice)
    return math.sqrt(np.dot(voice, voice) / sounding) if sounding else 0.0


def _voice_and_cymbals(
    voice: np.ndarray, score: Score, settings: SynthSettings, level: float, size: int
) -> np.ndarray:
    """The voice and the cymbals in a new buffer of `size` samples, silent after the voice."""
    mix = np.zeros(size)
    mix[: len(voice)] = voice
    if settings.cymbal_every is not None:
        _add_cymbals(mix[: len(voice)], score, settings, level)
    return mix


def _echoed(voice: np.ndarray, score: Score, settings: SynthSettings, level: float) -> np.ndarray:
    """Rule 25: the voice and cymbals convolved with the response by FFT, cut to the voice's length.
    The transforms are as long as the whole convolution, so nothing wraps round; each spectrum is
    multiplied in place."""
    n = len(voice)
    response = echo_response(settings)
    size = fast_length(n + len(response) - 1)
    spectrum = np.fft.rfft(_voice_and_cymbals(voice, score, settings, level, size))
    spectrum *= np.fft.rfft(response, size)
    return np.fft.irfft(spectrum, size)[:n].copy()  # a copy, so that the mix doesn't keep the padding


def _add_cymbals(mix: np.ndarray, score: Score, settings: SynthSettings, level: float) -> None:
    """Rule 24: each section hits from its start, every `cymbal_every` of its own half notes, while that
    is before its end. Times are exact, and wobble doesn't move them: a hit starts at the first sample
    at or after its time. A hit is noise differenced, so it is bright, and falls away. It is cut off by
    the end of the recording."""
    rate = settings.sample_rate_hz
    rng = np.random.default_rng([settings.seed, CYMBALS])
    length = round(CYMBAL_HIT_S * rate)
    fall = np.exp(-np.arange(length) / (CYMBAL_FALL_S * rate))
    peak = level * 10 ** (settings.cymbal_db / 20)
    for section in score.sections:
        spacing = settings.cymbal_every * Fraction(section.half_note_s)  # seconds
        for k in range(math.ceil((section.end - section.start) / spacing)):
            start = math.ceil((section.start + k * spacing) * rate)
            hit = np.diff(rng.standard_normal(length + 1)) * fall
            hit *= peak / np.max(np.abs(hit))
            stop = min(start + length, len(mix))
            if start < stop:
                mix[start:stop] += hit[: stop - start]


def _add_noise(mix: np.ndarray, settings: SynthSettings, level: float) -> None:
    """Rule 26: white noise over the whole recording, scaled so that its RMS is exactly
    `level * 10 ** (-snr / 20)`."""
    noise = np.random.default_rng([settings.seed, NOISE]).standard_normal(len(mix))
    noise *= level * 10 ** (-settings.noise_snr_db / 20) / math.sqrt(np.dot(noise, noise) / len(mix))
    mix += noise
