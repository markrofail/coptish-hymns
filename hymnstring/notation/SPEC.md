# String format

**Status: revised draft, format version 1, awaiting approval. No parser exists yet.**

This is the text form of string notation. The interpreter writes it, the round-trip check and renderer read it, and a cantor's fix edits it. Colours, pixel sizes and beat ticks belong to the renderer, not to this format.

## The idea

Here is the demo phrase from CONTEXT.md section 3 on one line:

```
p1 ltr: #1[A:2 ^ 1 v 1] ^ lē:~2 .2 v (lou:1 ^ 1 ^ 1)x3^ >1{i:*} a:2 !v2 #1[(a):2 ^ 1 v 1] v 4
```

Six rules make it work:

1. **One line per phrase.** `p1` is the phrase id and `ltr` or `rtl` the direction. Tokens follow in reading order, one space apart.
2. **Numbers are lengths** in half-note units: half = 1, full = 2, double = 4. Any whole number is allowed. Each section of a hymn has its own unit.
3. **Every note token is one bead.** Two notes with no move between them are a re-sung note on the same level, so same-level repeats need no sign of their own.
4. **Levels are never written.** Moves say up or down, and levels are worked out from them, with the phrase's lowest note as level 0. The text has no pitch names, semitones, seconds or BPM.
5. **Brackets only label notes.** Repeats and motifs are written out in full, so every bead in the drawing is a token in the text. Remove the brackets and you have the flat list of notes the synthesiser and round-trip check use.
6. **The signs are ASCII.** This is the canonical text, and the only form the writer outputs. Hazzat signs are accepted as input aliases, and the renderer and review page show them. Lyrics stay in their own script.

A move has no length of its own. It happens at the end of the stretch before it, so a note's length is always the distance from its bead to the next.

## Tokens

| Token | Canonical | Hazzat sign (shown, and accepted as input) | Meaning |
| --- | --- | --- | --- |
| Note | `2` | `2` | A plain note of that length |
| Vibrato | `~2` | `~2` | A wavy note of that length |
| Fast group | `>2{* ^ *}` | `→2{• ↑ •}` | Notes sung quickly. The group carries one length, usually 1 or 2, and its notes split it evenly. It may cross syllables. Each `*` is a note with a bead. |
| Pause | `.2` | `.2` | Silent, holding the current level |
| Step | `^` `v` `^2` `v3` | `↑` `↓` `↑2` `↓3` | A smooth slope, one level unless a size is given |
| Abrupt move | `!^` `!v` `!v2` | `↝↑` `↝↓` `↝↓2` | A corner, one level unless a size is given |
| Repeat | `(…)x3` `(…)x3^` `(…)x3v` | `(…)×3` `(…)×3↗` `(…)×3↘` | A bracket over the written-out notes: same level, rising or falling |
| Motif | `#1[…]` | `①[…]` | A labelled set: the same shape at the same starting level. The label holds across the whole hymn. |
| Shifted motif | `#1+1[…]` `#1-2[…]` | `①+1[…]` `①-2[…]` | **Extension.** The same shape, that many levels above or below the motif. |
| Syllable | `lou:1` | `lou:1` | Before a note: a new syllable starts on this note |
| Vowel label | `(a):2` | `(a):2` | Before a note: show (a) here, with no new syllable |
| Added letter | `<+ⲉ>` | `<+ⲉ>` | Inside a syllable: sung but not written (red) |
| Silent letter | `<-ϩ>` | `<-ϩ>` | Inside a syllable: written but not sung (gray) |

A note with no syllable or vowel label carries on the current syllable, including from the phrase before. A lyric can sit before a note, a vibrato note or a `*`.

Motif labels `#1` to `#20` have the aliases `①` to `⑳`. The writer leaves out a size of 1, so `^1` is accepted and written back as `^`.

### Moves: slope or corner

A slope and a corner differ in how the move sounds, not how big it is. `!` always means abrupt, whatever the size, and a leap is never written as a corner just because it is wide.

Who chooses the size:

- Strings converted from hazzat always use 1 per arrow, because hazzat says only higher or lower.
- Strings from audio use a size above 1 only when the measured leap is clearly bigger than the section's step, for example at least 1.5 steps.

The validator can't enforce this, because a string doesn't record where it came from. The rule binds whatever writes the string.

### Shifted motifs: an extension

**Hazzat can't express this.** Its `[...]①` means "repeat that set exactly", so a plain `#1` is strict: the same shape at the same starting level. `#1+1` is ours, for a melody that recurs a level higher or lower. It is drawn in the motif's colour with the shift in its label, such as `①+1`. A hazzat page would have to write those notes out with no reference.

The first occurrence of a motif in a hymn must be plain, because that occurrence sets the level the shift is measured from.

## One example for each rule

These are the rows of the table in CONTEXT.md section 2. The `p1 ltr:` prefix is left out except on the last row. Coptic syllables here are invented.

| Rule | Example | How it reads |
| --- | --- | --- |
| Stack, bottom to top | `1 ^ 1 ^ 2` | A stack of three marks, bottom mark first. Stacks need no token: reading order is token order. |
| Mark length | `1 ^ 2 ^ 4` | Half, full, double |
| Each separate mark | `2 2` | Two beads on one level. `4` would be one held note. |
| ↑ ↓ arrows | `2 ^ 2 v 2 ^3 2` | Slope up, slope down, then a measured leap of three levels |
| ↝ abrupt move | `2 !v2 2` | A corner, two levels down |
| ~ vibrating note | `~2 ^ ~4` | `~`, then `~~` lasting two notes |
| . pause | `2 .2 2 .4 2` | One dot, then two dots |
| → sing fast | `>1{i:*} ^ >2{ⲧⲓ:* ^ ⲛⲉ:* v ⲣⲁ:*}` | One fast note, then three syllables in the space of one full note |
| ( )×3 repeat | `(1 1 1)x3 ^ (1 ^ 1 ^ 1)x3^ (1 v 1 v 1)x3v` | Same level, rising, falling |
| [ ]① reference | `#1[2 ^ 1] v 2 #1[ⲡⲉ:2 ^ 1]` | The same motif twice, at the same level. The second one carries a new syllable. |
| Shifted motif (extension) | `#1[2 ^ 1] #1+1[2 ^ 1] v3 #1-1[2 ^ 1]` | The motif, then one level above it, then one level below it |
| Vowel in ( ) | `ⲁ:2 ^ 2 v (ⲁ):4` | Reminds the singer the vowel is still (a) |
| Red and gray letters | `ⲧ<+ⲉ>ⲛ:2 <-ϩ>ⲁ:2` | A red ⲉ in the first syllable, a gray ϩ in the second |
| Text direction | `p2 rtl: آ:2 ^ مين:2` | Still in reading order; the renderer mirrors the drawing. Some editors may display this line reordered. |

## The demo phrase, row by row

Each row matches the table in CONTEXT.md section 3. The tokens give 13 beads, as the drawing has, and 22 half-note units.

| # | Canonical | Hazzat signs | Level | Length |
| --- | --- | --- | --- | --- |
| 1 | `#1[A:2` | `①[A:2` | 1 | 2 |
| 2 | `^ 1` | `↑ 1` | 2 | 1 |
| 3 | `v 1]` | `↓ 1]` | 1 | 1 |
| 4 | `^ lē:~2` | `↑ lē:~2` | 2 | 2 |
| 5 | `.2` | `.2` | (silent) | 2 |
| 6 | `v (lou:1 ^ 1 ^ 1)x3^` | `↓ (lou:1 ↑ 1 ↑ 1)×3↗` | 1, 2, 3 | 1 each |
| 7 | `>1{i:*}` | `→1{i:•}` | 3 | 1 |
| 8 | `a:2` | `a:2` | 3 | 2 |
| 9 | `!v2 #1[(a):2 ^ 1 v 1]` | `↝↓2 ①[(a):2 ↑ 1 ↓ 1]` | 1, 2, 1 | 2, 1, 1 |
| 10 | `v 4` | `↓ 4` | 0 | 4 |

The lowest note is row 10, so it is level 0 and the phrase starts at level 1. Both motifs start at level 1, so the second is a plain `#1`.

Real strings hold the syllables as text prep gives them, in Coptic. The demo is romanised only because the drawing is.

Three details come from `reference/string_demo.svg`, which is otherwise only a style reference:

- A motif starts on its first note, and the move into it sits outside the brackets. The drawing colours those moves teal, not purple.
- A pause holds the level of the note before it, and the next move comes after the pause.
- The (a) label sits on the first note of row 9. The table mentions it on row 10, but both are under the same melisma.

## What makes a string invalid

The validator rejects a string when:

1. It has an unknown token, or a length or size below 1.
2. A phrase starts with a pause or a move, or ends on a move.
3. A move is followed by another move or a pause, so there is at most one move between two notes.
4. A repeat or motif starts with a pause or a move, or ends on a move. Moves into and out of a bracket sit outside it.
5. A fast group holds anything but `*` notes and moves, or a `*` appears outside one.
6. A repeat doesn't divide into its count of copies with the same shape, where each copy starts on the same level as the one before (no arrow), or the same number of levels higher (`^`) or lower (`v`). The count must be at least 2.
7. Two occurrences of a motif differ in shape, anywhere in the hymn.
8. Within one phrase, a plain motif starts on a different level from another plain occurrence, or a shifted one isn't that many levels from the plain one.
9. A shifted motif comes before the motif's first plain occurrence, or has a shift of 0.
10. A lyric isn't NFC, or contains anything but letters, combining marks and the letter marks above.

"Same shape" means the same moves, note kinds and lengths. Lyrics are ignored.

Rule 8 stops at the phrase because each phrase has its own level 0, so levels in two phrases can't be compared from the text. Across phrases, the round-trip check compares the motifs' measured pitch instead.

Checking that every syllable appears once and in order is also the round-trip check's job, because that needs the text.

## Grammar

```
line     = id " " dir ": " items
dir      = "ltr" | "rtl"
items    = item (" " item)*
item     = note | fast | pause | move | repeat | motif
note     = [lyric ":"] ["~"] length
fast     = ">" length "{" bead (" " [move " "] bead)* "}"
bead     = [lyric ":"] "*"
pause    = "." length
move     = ["!"] ("^" | "v") [length]
repeat   = "(" items ")" "x" count ["^" | "v"]
motif    = "#" label [("+" | "-") length] "[" items "]"
lyric    = syllable | "(" letters ")"
syllable = (letters | "<+" letters ">" | "<-" letters ">")+
```

`length`, `count` and `label` are whole numbers. `letters` is any run of letters and their combining marks, from both Coptic Unicode blocks or any other script.

Input aliases, each replaced by its canonical sign before parsing:

| Alias | Canonical |
| --- | --- |
| `↑` `↓` | `^` `v` |
| `↝` | `!` |
| `→` | `>` |
| `•` | `*` |
| `×` | `x` |
| `↗` `↘` | `^` `v` |
| `①` to `⑳` | `#1` to `#20` |

Parse-then-write tests use canonical text. One further test shows that input in hazzat signs normalises to the canonical form.

## In the JSON contracts

In `HymnString`, the id and direction are their own fields and `notation` holds `items`. `format_version` is 1. `HymnString` and `ReviewRecord` both carry it, because both store notation as text and can outlive a format change.
