# String format

**Status: draft for approval. No parser exists yet.**

This is the text form of string notation. The interpreter writes it, the round-trip check and renderer read it, and a cantor's fix edits it. Colours, pixel sizes and beat ticks belong to the renderer, not to this format.

## The idea

Here is the demo phrase from CONTEXT.md section 3 on one line:

```
p1 ltr: ①[A:2 ↑ 1 ↓ 1] ↑ lē:~2 .2 ↓ (lou:1 ↑ 1 ↑ 1)×3↗ →1{i:•} a:2 ↝↓2 ①[(a):2 ↑ 1 ↓ 1] ↓ 4
```

Five rules make it work:

1. **One line per phrase.** `p1` is the phrase id and `ltr` or `rtl` the direction. Tokens follow in reading order, one space apart.
2. **Numbers are lengths** in half-note units: half = 1, full = 2, double = 4. Any whole number is allowed.
3. **Every note token is one bead.** Two notes with no move between them are a re-sung note on the same level, so same-level repeats need no sign of their own.
4. **Levels are never written.** Moves say up or down, and levels are worked out from them, with the phrase's lowest note as level 0. Like hazzat, the text says only higher or lower. It has no pitch names, semitones, seconds or BPM.
5. **Brackets only label notes.** Repeats and motifs are written out in full, so every bead in the drawing is a token in the text. Remove the brackets and you have the flat list of notes the synthesiser and round-trip check use.

A move has no length of its own. It happens at the end of the stretch before it, so a note's length is always the distance from its bead to the next.

## Tokens

| Token | Written | Meaning |
| --- | --- | --- |
| Note | `2` | A plain note of that length |
| Vibrato | `~2` | A wavy note of that length |
| Fast stretch | `→2{• ↑ •}` | Notes sung quickly, sharing that length equally. Each `•` is a note with a bead. |
| Pause | `.2` | Silent, holding the current level |
| Step | `↑` `↓` | A slope of exactly one level |
| Abrupt move | `↝↑1` `↝↓2` | A corner: a jump of that many levels |
| Repeat | `(…)×3` `(…)×3↗` `(…)×3↘` | A bracket over the written-out notes, with its count and direction |
| Motif | `①[…]` | A labelled set, `①` to `⑳`. The label means the same motif across the whole hymn. |
| Syllable | `lou:1` | Before a note: a new syllable starts on this note |
| Vowel label | `(a):2` | Before a note: show (a) here, with no new syllable |
| Added letter | `<+ⲉ>` | Inside a syllable: sung but not written (red) |
| Silent letter | `<-ϩ>` | Inside a syllable: written but not sung (gray) |

A note with no syllable or vowel label carries on the current syllable, including from the phrase before. A lyric can sit before a note, a vibrato note or a `•`.

## One example for each rule

These are the 13 rows of the table in CONTEXT.md section 2. The `p1 ltr:` prefix is left out except on the last row. Coptic syllables here are invented.

| Rule | Example | How it reads |
| --- | --- | --- |
| Stack, bottom to top | `1 ↑ 1 ↑ 2` | A stack of three marks, bottom mark first. Stacks need no token: reading order is token order. |
| Mark length | `1 ↑ 2 ↑ 4` | Half, full, double |
| Each separate mark | `2 2` | Two beads on one level. `4` would be one held note. |
| ↑ ↓ arrows | `2 ↑ 2 ↓ 2` | Slope up, slope down |
| ↝ abrupt move | `2 ↝↓2 2` | A corner, two levels down |
| ~ vibrating note | `~2 ↑ ~4` | `~`, then `~~` lasting two notes |
| . pause | `2 .2 2 .4 2` | One dot, then two dots |
| → sing fast | `→1{i:•} ↑ →2{ⲧⲓ:• ↑ ⲛⲉ:• ↓ ⲣⲁ:•}` | One fast note, then three syllables in the space of one full note |
| ( )×3 repeat | `(1 1 1)×3 ↑ (1 ↑ 1 ↑ 1)×3↗ (1 ↓ 1 ↓ 1)×3↘` | Same level, rising, falling |
| [ ]① reference | `①[2 ↑ 1] ↓ 2 ①[ⲡⲉ:2 ↑ 1]` | The same motif twice. The second one carries a new syllable. |
| Vowel in ( ) | `ⲁ:2 ↑ 2 ↓ (ⲁ):4` | Reminds the singer the vowel is still (a) |
| Red and gray letters | `ⲧ<+ⲉ>ⲛ:2 <-ϩ>ⲁ:2` | A red ⲉ in the first syllable, a gray ϩ in the second |
| Text direction | `p2 rtl: آ:2 ↑ مين:2` | Still in reading order; the renderer mirrors the drawing. Some editors may display this line reordered. |

## The demo phrase, row by row

Each row matches the table in CONTEXT.md section 3. The tokens give 13 beads, as the drawing has, and 22 half-note units.

| # | Tokens | Level | Length |
| --- | --- | --- | --- |
| 1 | `①[A:2` | 1 | 2 |
| 2 | `↑ 1` | 2 | 1 |
| 3 | `↓ 1]` | 1 | 1 |
| 4 | `↑ lē:~2` | 2 | 2 |
| 5 | `.2` | (silent) | 2 |
| 6 | `↓ (lou:1 ↑ 1 ↑ 1)×3↗` | 1, 2, 3 | 1 each |
| 7 | `→1{i:•}` | 3 | 1 |
| 8 | `a:2` | 3 | 2 |
| 9 | `↝↓2 ①[(a):2 ↑ 1 ↓ 1]` | 1, 2, 1 | 2, 1, 1 |
| 10 | `↓ 4` | 0 | 4 |

The lowest note is row 10, so it is level 0 and the phrase starts at level 1.

Real strings hold the syllables as text prep gives them, in Coptic. The demo is romanised only because the drawing is.

Three details come from `reference/string_demo.svg`, not from the table:

- A motif starts on its first note, and the move into it sits outside the brackets. The drawing colours those moves teal, not purple.
- A pause holds the level of the note before it, and the next move comes after the pause.
- The (a) label sits on the first note of row 9. The table mentions it on row 10, but both are under the same melisma.

## What makes a string invalid

The validator rejects a string when:

1. It has an unknown token, or a length below 1.
2. A phrase starts with a pause or a move, or ends on a move.
3. A move is followed by another move or a pause, so there is at most one move between two notes.
4. A repeat or motif starts with a pause or a move, or ends on a move. Moves into and out of a bracket sit outside it.
5. A fast stretch holds anything but `•` notes and moves, or a `•` appears outside one.
6. A repeat doesn't divide into its count of copies with the same shape, where each copy starts on the same level as the one before (no arrow), one level higher (`↗`) or one level lower (`↘`). The count must be at least 2.
7. Two occurrences of a motif differ in shape, anywhere in the hymn.
8. A lyric isn't NFC, or contains anything but letters, combining marks and the letter marks above.

"Same shape" means the same moves, note kinds and lengths. Lyrics are ignored, and so is the level it starts on.

Checking that every syllable appears once and in order is the round-trip check's job, because that needs the text.

## Grammar

```
line     = id " " dir ": " items
dir      = "ltr" | "rtl"
items    = item (" " item)*
item     = note | fast | pause | move | repeat | motif
note     = [lyric ":"] ["~"] length
fast     = "→" length "{" bead (" " [move " "] bead)* "}"
bead     = [lyric ":"] "•"
pause    = "." length
move     = "↑" | "↓" | "↝" ("↑" | "↓") length
repeat   = "(" items ")" "×" count ["↗" | "↘"]
motif    = circled "[" items "]"
lyric    = syllable | "(" letters ")"
syllable = (letters | "<+" letters ">" | "<-" letters ">")+
```

`length` and `count` are whole numbers. `circled` is `①` to `⑳`. `letters` is any run of letters and their combining marks, from both Coptic Unicode blocks or any other script.

In the JSON `HymnString` contract, the id and direction are their own fields and `notation` holds `items`.

## Questions for approval

1. **Can a fast stretch hold several notes?** This draft says yes, because hazzat's arrow covers "the underlined part", sung in about one note's length. The demo only has one note. If a fast stretch is always one note, `→1{i:•}` can become `i:→1` and `•` goes away.
2. **Can a smooth move span more than one level?** This draft says no: the table says "one level", so a slope is always one level and anything wider is `↝`. The catch is that a wide but smooth leap would have to be drawn as a corner.
3. **Does a motif have to return on the same level?** This draft says no: it needs the same shape but can start higher or lower. Hazzat says "repeat that set exactly", so you may want it strict.
4. **Are hazzat's own signs right for the text form?** This draft uses `↑ ↓ ↝ → × ①` so it reads like the source. They are awkward to type by hand, so the review page would need buttons for them. ASCII stand-ins such as `^ v ! > x` would be easier to type but harder for a cantor to read.
