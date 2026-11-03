"""Sings a score: a stack of harmonics, shaped like the vowel "ah", made loud and quiet note by note.

The pitch comes from `pitch_at`, the one function that gives it (rule 13), so the voice and the true
pitch track can't disagree. Loudness is applied last, so a pause is exactly 0.0. The harmonics are
made BLOCK samples at a time, and the shaping pads its FFT to a length it handles well, so that a long
hymn doesn't ask for many times its own size in memory. Rule numbers are those in
docs/superpowers/plans/2026-11-02-synthesiser.md.
"""

import wave
from pathlib import Path

import numpy as np

from hymnstring.contracts import SynthSettings
from hymnstring.synth.fft import fast_length
from hymnstring.synth.score import Score, SungNote, sample_count
from hymnstring.synth.truth import pitch_at

MAX_HARMONICS = 30
RAMP_S = 0.01  # a run of notes fades in and out over at most this long
DIP_S = 0.015  # a re-sung note dips over at most this long on each side of its start
DIP_DEPTH = 0.9
FORMANTS = ((730, 90, 1.0), (1090, 110, 0.7), (2440, 170, 0.3))  # centre Hz, width Hz, gain: "ah"
BLOCK = 2**18  # samples, or frequencies, worked on at a time


def sing(score: Score, settings: SynthSettings) -> np.ndarray:
    """Rules 17 to 21: the dry voice, as many samples as `sample_count`."""
    rate, count = settings.sample_rate_hz, sample_count(score, settings)
    shaped = _vowel(_source(score, settings, count), rate)
    return shaped * _loudness(score, count, rate)


def write_wav(path: Path, samples: np.ndarray, sample_rate_hz: int) -> None:
    """Rule 27: mono 16-bit PCM, scaled so that its peak is 0.9 of full scale."""
    peak = np.max(np.abs(samples), initial=0.0)
    scale = 0.9 * 32767 / peak if peak > 0 else 0.0
    pcm = np.round(samples * scale).astype("<i2")
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(sample_rate_hz)
        out.writeframes(pcm.tobytes())


def _source(score: Score, settings: SynthSettings, count: int) -> np.ndarray:
    """Rule 18: the harmonics 1 to MAX_HARMONICS, each at 1/k, from the running phase of the pitch. A
    harmonic is left out wherever it would reach half the sample rate, and all of them where nothing
    sounds. The phase is carried over from one block to the next, so blocks make no difference."""
    rate = settings.sample_rate_hz
    source = np.zeros(count)
    phase = 0.0  # where the running phase stood at the end of the block before
    for lo in range(0, count, BLOCK):
        hi = min(lo + BLOCK, count)
        f0 = pitch_at(score, settings, np.arange(lo, hi) / rate)  # rule 17: sample n is at n / rate
        voiced = ~np.isnan(f0)
        hz = np.where(voiced, f0, 0.0)
        steps = 2 * np.pi * hz / rate
        steps[0] += phase
        running = np.cumsum(steps)
        phase = running[-1]
        for k in range(1, MAX_HARMONICS + 1):
            below_nyquist = voiced & (k * hz < rate / 2)
            source[lo:hi] += np.where(below_nyquist, np.sin(k * running), 0.0) / k
    return source


def _vowel(source: np.ndarray, rate: int) -> np.ndarray:
    """Rule 19: shape the whole source at once in the frequency domain, with no change of phase. The
    source is padded with silence to a length with only small factors, because an FFT of a length with
    a large prime factor takes several times the memory and time. The 0.15 is what every frequency
    keeps, so a high pitch has some voice left."""
    n = len(source)
    padded = fast_length(n)
    spectrum = np.fft.rfft(source, padded)
    del source  # sing passed it straight in, so this frees it for the inverse transform
    step = rate / padded
    for lo in range(0, len(spectrum), BLOCK):
        hz = np.arange(lo, min(lo + BLOCK, len(spectrum))) * step
        peaks = (gain * np.exp(-0.5 * ((hz - centre) / width) ** 2) for centre, width, gain in FORMANTS)
        spectrum[lo : lo + BLOCK] *= 0.15 + sum(peaks)
    return np.fft.irfft(spectrum, padded)[:n]


def _loudness(score: Score, count: int, rate: int) -> np.ndarray:
    """Rules 20 and 21: 1 while a note sounds and 0 otherwise, with a ramp at each end of a run of
    notes and a dip where a note is sung again."""
    times = np.arange(count) / rate  # rule 17
    loud = np.zeros(count)
    for run in _runs(score.notes):
        first, last = run[0], run[-1]
        begin, end = float(first.start), float(last.end)
        lo, hi = np.searchsorted(times, [begin, end])  # samples from `begin` up to, not including, `end`
        loud[lo:hi] = 1.0
        ramp_in = min(RAMP_S, float(first.end - first.start) / 2)  # both ramps sit inside their note
        ramp_out = min(RAMP_S, float(last.end - last.start) / 2)
        # a ramp is only the first or last RAMP_S of the run, plus a sample to be safe against rounding
        up = min(hi, np.searchsorted(times, begin + ramp_in) + 1)
        down = max(lo, np.searchsorted(times, end - ramp_out, side="right") - 1)
        loud[lo:up] = np.minimum(loud[lo:up], (times[lo:up] - begin) / ramp_in)
        loud[down:hi] = np.minimum(loud[down:hi], (end - times[down:hi]) / ramp_out)
        for before, note in zip(run, run[1:]):
            if note.cause != "pitch_change":  # its pitch is the cue when the pitch changes
                _dip(loud, times, before, note)
    return loud


def _runs(notes: tuple[SungNote, ...]) -> list[list[SungNote]]:
    """The notes that follow each other with no rest between, in groups."""
    runs: list[list[SungNote]] = []
    for note in notes:
        if runs and runs[-1][-1].end == note.start:
            runs[-1].append(note)
        else:
            runs.append([note])
    return runs


def _dip(loud: np.ndarray, times: np.ndarray, before: SungNote, note: SungNote) -> None:
    """Rule 21: a raised-cosine notch centred on the note's start, short enough to fit both notes."""
    start = float(note.start)
    reach = min(DIP_S, float((before.end - before.start) / 3), float((note.end - note.start) / 3))
    lo = np.searchsorted(times, start - reach, side="right")
    hi = np.searchsorted(times, start + reach, side="left")
    loud[lo:hi] *= 1 - DIP_DEPTH * 0.5 * (1 + np.cos(np.pi * (times[lo:hi] - start) / reach))
