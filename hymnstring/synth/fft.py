"""A length the FFT handles well, shared by the voice's shaping and the room's echo."""


def fast_length(n: int) -> int:
    """The smallest 2**a * 3**b * 5**c that is at least n. An FFT of a length with a large prime factor
    takes several times the memory and time, so a signal is padded with silence to a length like this."""
    best = 1 << (n - 1).bit_length()  # a power of two always qualifies
    power_of_five = 1
    while power_of_five < best:
        product = power_of_five
        while product < best:
            doublings = (-(-n // product) - 1).bit_length()  # how many it takes for the product to reach n
            best = min(best, product << doublings)
            product *= 3
        power_of_five *= 5
    return best
