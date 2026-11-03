"""An ear that shares nothing with the synthesiser: it measures samples with numpy alone.

The synthesiser's tests listen with these, so a mistake in the voice can't hide behind a matching
mistake in the measuring. Never import `hymnstring` here.
"""

import math

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
