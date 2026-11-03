"""An ear that shares nothing with the synthesiser: it measures samples with numpy alone.

The synthesiser's tests listen with these, so a mistake in the voice can't hide behind a matching
mistake in the measuring. Never import `hymnstring` here. `note_spans` and `plain_note_errors` read a
synthesis and its plan only by attribute, so they need no import either.
"""

import math
from bisect import bisect_right

import numpy as np

LOWEST_HZ, HIGHEST_HZ = 60, 1200  # the pitches measure_f0 looks for
BEST_SHARE = 0.9  # a peak counts if it reaches this share of the best one


def measure_f0(samples, rate, at_s, window_s=0.05):
    """The pitch in Hz at `at_s`, from `window_s` seconds of samples centred there. NaN if the window
    is silent or has no peak.

    It takes the normalised autocorrelation at every lag from 1200 Hz down to 60 Hz, then the smallest
    lag at a peak that reaches 0.9 of the best one, so that a pitch is not mistaken for its multiples.
    A parabola through the peak and its two neighbours refines it to a fraction of a sample.
    """
    centre, half = round(at_s * rate), round(window_s * rate / 2)
    window = np.asarray(samples[max(0, centre - half) : centre + half], dtype=float)
    n = len(window)
    energy = np.concatenate(([0.0], np.cumsum(window**2)))  # energy[j] is the first j squares, summed
    if energy[n] <= 0:
        return math.nan

    shortest, longest = math.ceil(rate / HIGHEST_HZ), min(math.floor(rate / LOWEST_HZ), n // 2)
    lags = np.arange(longest + 2)
    spectrum = np.fft.rfft(window, 2 * n)  # zero-padded, so the products below don't wrap round
    products = np.fft.irfft(spectrum * spectrum.conj())[: longest + 2]  # sum of w[i] * w[i + lag]
    scale = np.sqrt(energy[n - lags] * (energy[n] - energy[lags]))  # the energy of the two stretches
    correlation = np.divide(products, scale, out=np.zeros_like(products), where=scale > 0)

    inside = correlation[1:-1]  # a peak beats the lag before it and matches or beats the one after
    best = correlation[shortest : longest + 1].max()
    peaks = (inside > correlation[:-2]) & (inside >= correlation[2:]) & (inside >= BEST_SHARE * best)
    found = np.flatnonzero(peaks) + 1  # +1: the lag of inside[0] is 1
    found = found[(found >= shortest) & (found <= longest)]
    if len(found) == 0:
        return math.nan

    lag = int(found[0])
    before, here, after = correlation[lag - 1 : lag + 2]
    return rate / (lag + 0.5 * (before - after) / (before - 2 * here + after))


def level_db(samples, rate, start_s, end_s):
    """The RMS of the samples from `start_s` to `end_s`, in dB. Exact silence is -inf."""
    window = samples[max(0, round(start_s * rate)) : round(end_s * rate)]
    rms = math.sqrt(float(np.mean(np.square(window))))
    return 20 * math.log10(rms) if rms > 0 else -math.inf


def band_db(samples, rate, low_hz, high_hz):
    """The energy between two frequencies in the spectrum of all the samples, in dB."""
    hz = np.fft.rfftfreq(len(samples), 1 / rate)
    spectrum = np.fft.rfft(samples)[(hz >= low_hz) & (hz <= high_hz)]
    energy = float(np.sum(np.abs(spectrum) ** 2))
    return 10 * math.log10(energy) if energy > 0 else -math.inf


def cents_above(hz, reference_hz):
    return 1200 * math.log2(hz / reference_hz)


def largest_prime_factor(n):
    factor = 2
    while factor * factor <= n:
        if n % factor == 0:
            n //= factor
        else:
            factor += 1
    return n


def note_spans(truth):
    """The (start, end) seconds of each note: it lasts until the next note or breath starts, or the
    hymn ends."""
    marks = {n.start_s for n in truth.note_starts.notes} | {b.start_s for b in truth.note_starts.breaths}
    marks = sorted(marks | {truth.pulse_unit.sections[-1].end_s})
    return [(n.start_s, marks[bisect_right(marks, n.start_s)]) for n in truth.note_starts.notes]


def plain_note_errors(synthesis, hymn, slope_s):
    """How far, in cents, the audio's pitch is from the true pitch at the centre of each plain note: one
    the plan calls a note or a fast bead, at least 80 ms long, with no slide within 40 ms of its centre."""
    track = synthesis.truth.pitch_track
    events = hymn.events
    notes = [(i, event) for i, event in enumerate(events) if event.kind != "pause"]
    errors = []
    for (start, end), (i, event) in zip(note_spans(synthesis.truth), notes, strict=True):
        centre = (start + end) / 2
        slides = i + 1 < len(events) and events[i + 1].slides_in  # a smooth move leads to the next note
        slide_from = end - min(slope_s, (end - start) / 2)  # it takes the last part of the note
        if event.kind == "vibrato" or end - start < 0.08 or (slides and slide_from - centre <= 0.04):
            continue
        heard = measure_f0(synthesis.samples, synthesis.sample_rate_hz, centre)
        errors.append(abs(cents_above(heard, track.f0_hz[round(centre / track.hop_s)])))  # nearest frame
    return errors
