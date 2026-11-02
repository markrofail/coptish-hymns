"""Draws a phrase as one SVG string, and a hymn as an HTML page. Lengths are strictly proportional."""

import unicodedata
from fractions import Fraction
from math import ceil, floor
from xml.sax.saxutils import escape

from hymnstring.notation.flatten import FlatNote, FlatPause, flatten
from hymnstring.notation.model import Hymn, Phrase, Syllable, Vowel

UNIT_PX = 12.5  # a half note
LEVEL_PX = 20
MARGIN_X = 40
STROKE = 3
BEAD_R = 3
SLOPE_PX = 6
TEAL = "#1D9E75"
GRAY = "#888780"
LABEL = "#5F5E5A"
INK = "#2C2C2A"
ADDED = "#C8402A"
SILENT = "#A3A29C"
MOTIF_COLOURS = ("#7F77DD", "#D85A30", "#378ADD", "#BA7517", "#D4537E", "#639922")
LYRIC_SIZE = 14
LABEL_SIZE = 12
LYRIC_GAP = 3
FONT = "-apple-system, 'Helvetica Neue', Helvetica, Arial, 'Noto Sans Coptic', sans-serif"

TOP_PX = 12  # between the canvas top and the highest annotation
LYRIC_DROP = 28  # lyric baseline below the lowest level
BOTTOM_PX = 14  # canvas end below the lyric baseline
WAVE_PX = 3  # width of one half-wave of a vibrato


def _n(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def _letters(lyric: Syllable | Vowel) -> str:
    if isinstance(lyric, Vowel):
        return f"({lyric.letters})"
    return "".join(part.text for part in lyric.parts)


def _size(lyric: Syllable | Vowel) -> int:
    return LABEL_SIZE if isinstance(lyric, Vowel) else LYRIC_SIZE


def _text_width(text: str, size: int) -> Fraction:
    """Estimated width. Combining marks add none."""
    return Fraction(62, 100) * size * sum(not unicodedata.category(c).startswith("M") for c in text)


def _spans(lyric: Syllable) -> str:
    parts = []
    for part in lyric.parts:
        text = escape(part.text)
        colour = {"added": ADDED, "silent": SILENT}.get(part.mark)
        parts.append(f'<tspan fill="{colour}">{text}</tspan>' if colour else text)
    return "".join(parts)


def hymn_unit(hymn: Hymn) -> float:
    """The smallest unit, at least a half note, at which no lyric runs into the next."""
    need = Fraction(str(UNIT_PX))
    for phrase in hymn.phrases:
        owner, distance = None, Fraction(0)  # the last lyric, and the length since it
        for event in flatten(phrase.items).events:
            lyric = event.lyric if isinstance(event, FlatNote) else None
            if lyric is not None:
                if owner is not None:
                    width = _text_width(_letters(owner), _size(owner))
                    need = max(need, (width + LYRIC_GAP) / distance)
                owner, distance = lyric, Fraction(0)
            distance += event.length
    return ceil(need * 100) / 100


def render_hymn(hymn: Hymn) -> str:
    unit = hymn_unit(hymn)
    figures = "\n".join(f"<figure>\n{render_phrase(p, unit)}\n</figure>" for p in hymn.phrases)
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>String notation</title>\n"
        "<style>body{margin:16px;background:#fff}figure{margin:0 0 8px;overflow-x:auto}"
        "svg{max-width:none}</style>\n</head>\n<body>\n" + figures + "\n</body>\n</html>\n"
    )


def render_phrase(phrase: Phrase, unit: float = UNIT_PX) -> str:
    return _Drawing(phrase, unit).svg()


class _Drawing:
    def __init__(self, phrase: Phrase, unit: float):
        self.phrase = phrase
        self.rtl = phrase.direction == "rtl"
        flat = flatten(phrase.items)
        self.flat, self.events = flat, flat.events
        count = len(self.events)

        # x of every event's start, then the end. Lengths are the only thing that sets them.
        total = Fraction(0)
        self.xs = []
        for event in self.events:
            self.xs.append(MARGIN_X + unit * float(total))
            total += event.length
        self.xs.append(MARGIN_X + unit * float(total))

        # y with the lowest level at 0 and up negative; shifted down once the annotations are placed.
        lowest = min((e.level for e in self.events), default=0)
        self.ys = [-LEVEL_PX * (e.level - lowest) for e in self.events] + [0]

        self.lyrics = [
            (i, e.lyric) for i, e in enumerate(self.events) if isinstance(e, FlatNote) and e.lyric
        ]
        right = max([self.xs[count]] + [self.xs[i] + float(_text_width(_letters(l), _size(l))) for i, l in self.lyrics])
        self.width = right + MARGIN_X

        self.marks = self.place_marks()
        top = min([m["base"] - m["height"] for m in self.marks] + [min(self.ys[:count], default=0) - 6])
        self.shift = TOP_PX - top
        self.height = self.shift + LYRIC_DROP + BOTTOM_PX

    # -- helpers --

    def X(self, x: float) -> float:
        return self.width - x if self.rtl else x

    def point(self, x: float, y: float) -> str:
        return f"{_n(self.X(x))} {_n(y + self.shift)}"

    def path(self, cls: str, d: str, stroke: str, width: float = STROKE, extra: str = "") -> str:
        return f'<path class="{cls}" d="{d}" stroke="{stroke}" stroke-width="{_n(width)}"{extra}/>'

    def motif_at(self, index: int, inside: bool) -> str:
        """The colour of the innermost motif holding the event, or, for a move, spanning it."""
        found = TEAL
        for m in self.flat.motifs:  # outer motifs come first, so the last match is innermost
            if (m.first_event < index if inside else m.first_event <= index) and index < m.end_event:
                found = MOTIF_COLOURS[(m.label - 1) % len(MOTIF_COLOURS)]
        return found

    # -- annotations --

    def place_marks(self) -> list[dict]:
        """Breaths, then motifs, then repeats, smaller first. Each rises over what it overlaps."""
        placed, marks = [], []

        def put(kind, first, end, x0, x1, height, **fields):
            base = min(self.ys[first:end])
            for left, right, top in placed:
                if left < x1 and x0 < right:
                    base = min(base, top)
            placed.append((x0, x1, base - height))
            marks.append(dict(kind=kind, base=base, height=height, **fields))

        for i, event in enumerate(self.events):
            if isinstance(event, FlatPause):
                cx = (self.xs[i] + self.xs[i + 1]) / 2
                put("breath", i, i + 1, cx - 2.5, cx + 3, 20, cx=cx)
        for m in sorted(self.flat.motifs, key=lambda m: m.end_event - m.first_event):
            sign = f"{m.shift:+d}" if m.shift else ""
            name = chr(0x2460 + m.label - 1) if m.label <= 20 else f"#{m.label}"
            self.put_label(put, "motif", m.first_event, m.end_event, name + sign, 24)
        for r in sorted(self.flat.repeats, key=lambda r: r.end_event - r.first_event):
            arrows = ("↖", "↙") if self.rtl else ("↗", "↘")
            more = f" {arrows[r.step < 0]}{abs(r.step) if abs(r.step) > 1 else ''}" if r.step else ""
            self.put_label(put, "repeat", r.first_event, r.end_event, f"×{r.count}{more}", 42)
        return marks

    def put_label(self, put, kind, first, end, text, height):
        x0, x1 = self.xs[first], self.xs[end]
        half = float(_text_width(text, LABEL_SIZE)) / 2
        centre = (x0 + x1) / 2
        if kind == "repeat":
            x0, x1 = min(x0, centre - half), max(x1, centre + half)
        else:
            x0, x1 = centre - half, centre + half
        put(kind, first, end, x0, x1, height, text=text, centre=centre, bracket=(self.xs[first], self.xs[end]))

    def annotation(self, mark: dict) -> str:
        base, kind = mark["base"], mark["kind"]
        p = self.point
        if kind == "breath":
            cx, cy = mark["cx"], base - 16
            tail = f"M{p(cx + 2.3, cy + 0.5)} Q{p(cx + 2.8, cy + 5.5)} {p(cx - 1.2, cy + 8.5)}"
            return (
                f'<g class="breath"><circle cx="{_n(self.X(cx))}" cy="{_n(cy + self.shift)}" r="2.5" fill="{LABEL}"/>'
                f'<path d="{tail}" fill="none" stroke="{LABEL}" stroke-width="1.5" stroke-linecap="round"/></g>'
            )
        baseline = base - (12 if kind == "motif" else 30)
        text = (
            f'<text class="{kind}-label" x="{_n(self.X(mark["centre"]))}" y="{_n(baseline + self.shift)}" '
            f'text-anchor="middle" font-size="{LABEL_SIZE}" fill="{LABEL}">{escape(mark["text"])}</text>'
        )
        if kind == "motif":
            return text
        x0, x1 = mark["bracket"]
        d = f"M{p(x0, base - 16)} L{p(x0, base - 22)} L{p(x1, base - 22)} L{p(x1, base - 16)}"
        return f'<path class="repeat-bracket" d="{d}" fill="none" stroke="{LABEL}" stroke-width="1"/>\n{text}'

    # -- strings --

    def stretch(self, i: int, stop: float) -> str:
        event, x, y = self.events[i], self.xs[i], self.ys[i]
        p = self.point
        if isinstance(event, FlatPause):
            return self.path("pause", f"M{p(x, y)} L{p(stop, y)}", GRAY, 1.5, ' stroke-dasharray="0.5 4"')
        colour = self.motif_at(i, inside=False)
        if event.kind == "fast":
            return self.path("fast", f"M{p(x, y)} L{p(stop, y)}", colour, 1.5, ' stroke-dasharray="3 2.5" stroke-linecap="butt"')
        if event.kind == "vibrato":
            half = floor((stop - x) / WAVE_PX + 1e-9)
            d = f"M{p(x, y)}"
            if half:
                d += f" Q{p(x + WAVE_PX / 2, y - 7)} {p(x + WAVE_PX, y)}"
                d += "".join(f" T{p(x + WAVE_PX * k, y)}" for k in range(2, half + 1))
            return self.path("wave", f"{d} L{p(stop, y)}", colour)
        return self.path("stretch", f"M{p(x, y)} L{p(stop, y)}", colour)

    def strings(self) -> list[str]:
        out, p = [], self.point
        for i in range(len(self.events)):
            x, y, end = self.xs[i], self.ys[i], self.xs[i + 1]
            after = self.events[i + 1] if i + 1 < len(self.events) else None
            move = after.move if isinstance(after, FlatNote) else None
            slope = move is not None and not move.abrupt
            run = min(SLOPE_PX, (end - x) / 2) if slope else 0
            out.append(self.stretch(i, end - run))
            if move is None:
                continue
            colour, y2 = self.motif_at(i + 1, inside=True), self.ys[i + 1]
            if slope:
                a, b = end - run, end - run / 2
                out.append(self.path("slope", f"M{p(a, y)} C{p(b, y)} {p(b, y2)} {p(end, y2)}", colour))
            elif move.change:
                out.append(self.path("corner", f"M{p(end, y)} L{p(end, y2)}", colour))
            else:
                out.append(self.path("tick", f"M{p(end, y - 6)} L{p(end, y + 6)}", colour, 1.5))
        return out

    def beads(self) -> list[str]:
        return [
            f'<circle class="bead" cx="{_n(self.X(self.xs[i]))}" cy="{_n(self.ys[i] + self.shift)}" r="{BEAD_R}" '
            f'fill="{self.motif_at(i, inside=False)}"/>'
            for i, e in enumerate(self.events)
            if isinstance(e, FlatNote)
        ]

    def lyric_texts(self) -> list[str]:
        out = []
        y = _n(self.shift + LYRIC_DROP)
        side = ' text-anchor="end" direction="rtl"' if self.rtl else ""
        for i, lyric in self.lyrics:
            x = _n(self.X(self.xs[i]))
            if isinstance(lyric, Vowel):
                out.append(
                    f'<text class="vowel" x="{x}" y="{y}"{side} font-size="{LABEL_SIZE}" fill="{LABEL}">{escape(_letters(lyric))}</text>'
                )
                continue
            fast = self.events[i].kind == "fast"
            line = ' text-decoration="underline"' if fast else ""
            out.append(
                f'<text class="lyric" x="{x}" y="{y}"{side}{line} font-size="{LYRIC_SIZE}" fill="{INK}">{_spans(lyric)}</text>'
            )
        return out

    def svg(self) -> str:
        w, h = _n(self.width), _n(self.height)
        lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{_n(self.width * 2)}" height="{_n(self.height * 2)}" '
            f'viewBox="0 0 {w} {h}" role="img" font-family="{FONT}">',
            f"<title>Phrase {escape(self.phrase.phrase_id)}</title>",
            f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
            '<g fill="none" stroke-linecap="round" stroke-linejoin="round">',
            *self.strings(),
            "</g>",
            *self.beads(),
            *(self.annotation(m) for m in self.marks),
            *self.lyric_texts(),
            "</svg>",
        ]
        return "\n".join(lines)
