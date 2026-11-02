# String format

**Status: format version 1, approved by the owner on 2026-11-01.**

This is the text form of string notation. The interpreter writes it, the round-trip check and renderer read it, and a cantor's fix edits it. Colours, pixel sizes and beat ticks belong to the renderer, not to this format.

## The idea

Here is the demo phrase from CONTEXT.md section 3 on one line:

```
p1 ltr: #1[A:2 ^ 1 v 1] ^ lē:~2 .2 v (lou:1)x3^ >1{i:*} a:2 !v2 #1[(a):2 ^ 1 v 1] v 4
```

Six rules make it work:

1. **One line per phrase.** `p1` is the phrase id and `ltr` or `rtl` the direction. Tokens follow in reading order, one space apart.
2. **Numbers are lengths** in half-note units: half = 1, full = 2, double = 4. Any whole number is allowed, but a phrase can expand to at most 10,000 notes, pauses and moves, and a hymn to at most 100,000. Joins between a repeat's copies are not counted. Each section of a hymn has its own unit.
3. **Every written note is one bead.** A repeat writes its notes once, and its copies add the rest. Two notes with no move between them are a re-sung note on the same level, so same-level repeats need no sign of their own.
4. **Levels are never written.** Moves say up or down, and levels are worked out from them, with the phrase's lowest note as level 0. The text has no pitch names, semitones, seconds or BPM.
5. **Brackets label notes, and a repeat holds one copy.** A motif bracket only labels notes. A repeat bracket writes its body once, with a count, so the text can have fewer tokens than the drawing has beads. Remove the brackets and expand the repeats, and you have the flat list of notes the synthesiser and round-trip check use.
6. **The signs are ASCII.** This is the canonical text, and the only form the writer outputs. Hazzat signs are accepted as input aliases, and the renderer and review page show them. Lyrics stay in their own script.

A move has no length of its own. It happens at the end of the stretch before it, so a note's length is always the distance from its bead to the next.

## Tokens

| Token | Canonical | Hazzat sign (shown, and accepted as input) | Meaning |
| --- | --- | --- | --- |
| Note | `2` | `2` | A plain note of that length |
| Vibrato | `~2` `~4` | `~` `~~` | A wavy note of that length. A run of n tildes is a vibrato of length 2n. |
| Fast group | `>2{* ^ *}` | `→2{• ↑ •}` | Notes sung quickly. The group carries one length, usually 1 or 2, and its notes split it evenly. It may cross syllables. Each `*` is a note with a bead. |
| Pause | `.2` `.4` | `.` `..` | Silent, holding the current level. A run of n dots is a pause of length 2n. |
| Step | `^` `v` `^2` `v3` | `↑` `↓` `↑2` `↓3` | A smooth slope, one level unless a size is given |
| Abrupt move | `!` `!^` `!v` `!v2` | `↝` `↝↑` `↝↓` `↝↓2` | A corner, one level unless a size is given. Bare `!` is a quick move on with no change of level, drawn as a short tick across the string. |
| Same-level join | `=` | none | Only as a phrase's join (see Phrase joins): the same level as the previous phrase's last note |
| Repeat | `(…)x3` `(…)x3^` `(…)x3v` `(…)x3^2` | `(…)×3` `(…)×3↗` `(…)×3↘` `(…)×3↗2` | A bracket over one written copy, repeated 3 times in all: each copy on the same level, or a level higher or lower than the one before (2 levels in the last form) |
| Motif | `#1[…]` | `①[…]` | A labelled set: the same shape at the same starting level. The label holds across the whole hymn. |
| Motif copy | `#1[…]` | `[...]①` | Input only: the first `#1` is repeated exactly, with no lyrics, and is written back as a full `#1[…]`. `[...]#1` is accepted too. See Motif copies. |
| Shifted motif | `#1+1[…]` `#1-2[…]` | `①+1[…]` `①-2[…]` | **Extension.** The same shape, that many levels above or below the motif. |
| Syllable | `lou:1` | `lou:1` | Before a note: a new syllable starts on this note |
| Vowel label | `(a):2` | `(a):2` | Before a note: show (a) here, with no new syllable |
| Added letter | `<+ⲉ>` | `<+ⲉ>` | Inside a syllable: sung but not written (red) |
| Silent letter | `<-ϩ>` | `<-ϩ>` | Inside a syllable: written but not sung (gray) |

A note with no syllable or vowel label carries on the current syllable, including from the phrase before. A lyric can sit before a note, a vibrato note or a `*`.

Motif labels `#1` to `#20` have the aliases `①` to `⑳`. The writer leaves out a size or step of 1, so `^1` is accepted and written back as `^`, and `x3^1` as `x3^`.

### Moves: slope or corner

A slope and a corner differ in how the move sounds, not how big it is. `!` always means abrupt, whatever the size, and that includes size zero: a bare `!` is a corner with no change of level, a short tick across the string. A leap is never written as a corner just because it is wide. A bare `!` takes no size, so `!2` is not a token.

Who chooses the size:

- Strings converted from hazzat always use 1 per arrow, because hazzat says only higher or lower.
- Strings from audio use a size above 1 only when the measured leap is clearly bigger than the section's step, for example at least 1.5 steps.

The validator can't enforce this, because a string doesn't record where it came from. The rule binds whatever writes the string.

### Repeats: one copy, written once

A repeat writes its body once and says how many times it is sung.

- Forms: `(body)xN`, `(body)xN^`, `(body)xNv`, `(body)xN^K`, `(body)xNvK`. There is no space inside the token, so `(1)x3^2` rises 2 levels per copy and `(1)x3^ 2` is a repeat followed by a note.
- `body` holds one copy. `N` is the total number of copies, at least 2. `K` is the levels per copy, at least 1, and a `K` of 1 is left out.
- Copy `i`, counting from 0, starts at `start + i * delta`, where `start` is the level of the repeat's first note. `delta` is 0 for `xN`, `+K` for `^` and `-K` for `v`.
- Between consecutive copies the join is a smooth move of whatever size the start levels need. If no level change is needed there is no move, so the next copy's first note is a re-sung note.
- The renderer writes the copies out in full, under a bracket. Lyric labels (syllables and vowel labels) go on the first copy only, so every note in a later copy carries on the current syllable.
- A repeat whose copies carry different syllables can't use this form. Write the notes out; a motif can label them.

Examples, with levels counted from the first note:

| Text | Levels | Note |
| --- | --- | --- |
| `(1)x3` | 0, 0, 0 | Three re-sung notes |
| `(lou:1)x3^` | 0, 1, 2 | Each copy a level higher |
| `(1)x3v2` | 0, -2, -4 | Each copy two levels lower |
| `(1 ^ 1)x2` | 0, 1, 0, 1 | A smooth `v` join between the copies |
| `(1 ^ 1)x3^` | 0, 1, 1, 2, 2, 3 | Each copy starts where the last one ended, so no move between copies |

### Phrase joins and chains

A phrase may begin with one optional **join**, before its first note: a move from the previous phrase's last note. For example `p2 ltr: v2 1 ^ 2` starts 2 levels below where the phrase before it ended.

- Any move form is allowed as a join: `^`, `v2`, `!`, `!v2`.
- `=` is also a join. It means the same level as the previous phrase's last note. A chain needs a way to say this, and sizes below 1 are invalid. `=` is valid only as a join, and has no hazzat sign.
- After a trailing pause, the previous level is the level the pause held.
- The first phrase of a hymn can't have a join.
- A join is followed by a note, a fast group, or a bracket that starts with one, never by a pause or another move.
- A **chain** is a run of phrases linked by joins. A phrase with no join starts a new chain.
- Each phrase is still drawn with its own lowest note as level 0. Chains exist so levels can be compared.
- Inside a chain levels can be compared, so motifs are checked strictly. Across chains the text has no shared level, so motifs are checked by shape only and the round-trip check compares their measured pitch. When every phrase after the first has a join, the whole hymn is one chain and motifs are checked strictly everywhere.
- In the JSON `HymnString`, `notation` holds the join and the items.

Example: `p1` and `p2` are one chain, so both `#1` start on the same level. `p3` has no join and starts a new chain.

```
p1 ltr: #1[2 ^ 1] 2
p2 ltr: v #1[2 ^ 1]
p3 ltr: #1[2 ^ 1] 4
```

### Motif copies

A later `[...]#1` with no notes inside, whose label comes after the bracket, copies the first occurrence's shape without its lyrics. The three dots are written as they are. `[...]①` is the hazzat form. It is resolved when the hymn is parsed, across phrases, and the writer outputs the full canonical occurrence, such as `#1[2 ^ 1 v 1]`. It is a plain occurrence, so it starts on the same level as the other plain ones. With no earlier occurrence of the label it is an error. There is no shifted form of it.

Example: `#1[2 ^ 1] v 2 [...]#1` is written back as `#1[2 ^ 1] v 2 #1[2 ^ 1]`, the second motif at the same level as the first.

### Shifted motifs: an extension

**Hazzat can't express this.** Its `[...]①` means "repeat that set exactly", so a plain `#1` is strict: the same shape at the same starting level. `#1+1` is ours, for a melody that recurs a level higher or lower. It is drawn in the motif's colour with the shift in its label, such as `①+1`. A hazzat page would have to write those notes out with no reference.

The first occurrence of a motif in a hymn must be plain, because that occurrence sets the level the shift is measured from.

### Strict motifs

Within a chain, all plain occurrences of a motif must start on the same level, and an occurrence `#1+n` must start `n` levels from the plain occurrences in that chain. If the chain has no plain occurrence, the shifted ones are compared with each other instead: `#1+1` and `#1+2` must start one level apart. So `#1+1[2] #1+2[2]` in a chain of its own is invalid, because both start on the same level. "Same shape" is compared after expanding repeats, so `#1[(1)x3 ^ 2]` and `#1[1 1 1 ^ 2]` have the same shape. A motif inside a level-changing repeat occurs at a new level in each copy, so a motif there is invalid: every motif is checked strictly within its chain.

### Extensions

**Hazzat can't express these.** They are ours.

- Shifted motifs (`#1+1[…]`), above.
- Half-length pauses and vibratos: `.1`, `~1`, and any odd length. Hazzat's dots and tildes count whole notes, so they have no sign.
- Move sizes above 1, which only strings from audio use.

## One example for each rule

These are the rows of the table in CONTEXT.md section 2. The `p1 ltr:` prefix is left out except on the join and last rows. Coptic syllables here are invented. Every example in this table is canonical and survives parse-then-write unchanged.

| Rule | Example | How it reads |
| --- | --- | --- |
| Stack, bottom to top | `1 ^ 1 ^ 2` | A stack of three marks, bottom mark first. Stacks need no token: reading order is token order. |
| Mark length | `1 ^ 2 ^ 4` | Half, full, double |
| Each separate mark | `2 2` | Two beads on one level. `4` would be one held note. |
| ↑ ↓ arrows | `2 ^ 2 v 2 ^3 2` | Slope up, slope down, then a measured leap of three levels |
| ↝ abrupt move | `2 !v2 2 ! 2` | A corner, two levels down, then a bare `!`: two beads on one level with a short tick between them |
| ~ vibrating note | `~2 ^ ~4` | `~`, then `~~` lasting two notes. Hazzat signs write them `~` and `~~`. |
| . pause | `2 .2 2 .4 2` | One dot, then two dots. Hazzat signs write them `.` and `..`. |
| → sing fast | `>1{i:*} ^ >2{ⲧⲓ:* ^ ⲛⲉ:* v ⲣⲁ:*}` | One fast note, then three syllables in the space of one full note |
| ( )×3 repeat | `(1)x3 ^ (1)x3^ (1)x3v` | Three notes on one level, a step up, then three copies each a level higher, then three each a level lower |
| [ ]① reference | `#1[2 ^ 1] v 2 #1[ⲡⲉ:2 ^ 1]` | The same motif twice, at the same level. The second one carries a new syllable. |
| Shifted motif (extension) | `#1[2 ^ 1] #1+1[2 ^ 1] v3 #1-1[2 ^ 1]` | The motif, then one level above it, then one level below it |
| Vowel in ( ) | `ⲁ:2 ^ 2 v (ⲁ):4` | Reminds the singer the vowel is still (a) |
| Red and gray letters | `ⲧ<+ⲉ>ⲛ:2 <-ϩ>ⲁ:2` | A red ⲉ in the first syllable, a gray ϩ in the second |
| Phrase join | `p2 ltr: v2 1 ^ 2` | Read after a first phrase. A move from that phrase's last note comes before the first note, here two levels down. |
| Text direction | `p2 rtl: آ:2 ^ مين:2` | Still in reading order; the renderer mirrors the drawing. Some editors may display this line reordered. |

## The demo phrase, row by row

Each row matches the table in CONTEXT.md section 3. The text has 11 note tokens, and expanding the repeat gives 13 beads, as the drawing has. The lengths total 22 half-note units.

| # | Canonical | Hazzat signs | Level | Length |
| --- | --- | --- | --- | --- |
| 1 | `#1[A:2` | `①[A:2` | 1 | 2 |
| 2 | `^ 1` | `↑ 1` | 2 | 1 |
| 3 | `v 1]` | `↓ 1]` | 1 | 1 |
| 4 | `^ lē:~2` | `↑ lē:~` | 2 | 2 |
| 5 | `.2` | `.` | (silent) | 2 |
| 6 | `v (lou:1)x3^` | `↓ (lou:1)×3↗` | 1, 2, 3 | 1 each |
| 7 | `>1{i:*}` | `→1{i:•}` | 3 | 1 |
| 8 | `a:2` | `a:2` | 3 | 2 |
| 9 | `!v2 #1[(a):2 ^ 1 v 1]` | `↝↓2 ①[(a):2 ↑ 1 ↓ 1]` | 1, 2, 1 | 2, 1, 1 |
| 10 | `v 4` | `↓ 4` | 0 | 4 |

The lowest note is row 10, so it is level 0 and the phrase starts at level 1. Both motifs start at level 1, so the second is a plain `#1`.

The repeat in row 6 is one copy, `lou:1`, sung 3 times, each a level higher. The drawing's three beads come from the expansion.

Real strings hold the syllables as text prep gives them, in Coptic. The demo is romanised only because the drawing is.

Three details come from `reference/string_demo.svg`, which is otherwise only a style reference:

- A motif starts on its first note, and the move into it sits outside the brackets. The drawing colours those moves teal, not purple.
- A pause holds the level of the note before it, and the next move comes after the pause.
- The (a) label sits on the first note of row 9. The table mentions it on row 10, but both are under the same melisma.

## What makes a string invalid

The validator rejects a string when:

1. It has an unknown token, or a length, move size, repeat level step or shift below 1, or a repeat count below 2, or a phrase that expands to more than 10,000 notes, pauses and moves, or a hymn to more than 100,000. A bare `!` and `=` are the only moves with no size.
2. The first phrase of the hymn has a join, or `=` appears anywhere but as a phrase's join.
3. A phrase, after its join, starts with a pause or a move, or ends on a move. A join is followed by a note, a fast group, or a bracket that starts with one.
4. A move is followed by another move or a pause, so there is at most one move between two notes. The join counts as the move before the phrase's first note.
5. A repeat or motif body starts with a pause or a move, or ends on a move. Moves into and out of a bracket sit outside it.
6. A fast group holds anything but `*` notes and moves, or a `*` appears outside one.
7. Two occurrences of a motif differ in shape, anywhere in the hymn, after expanding repeats.
8. Within a chain, a plain motif starts on a different level from another plain occurrence, or a shifted one isn't that many levels from the plain ones in that chain, or, with no plain one in the chain, from the other shifted ones.
9. A shifted motif comes before the motif's first plain occurrence in the hymn, or has a shift of 0. A `[...]` copy has no earlier occurrence of its label, or has a shift.
10. A motif sits inside a repeat that changes level (`^` or `v`).
11. A lyric isn't NFC, or contains anything but letters, combining marks and the letter marks above.

"Same shape" means the same moves, note kinds and lengths. Lyrics are ignored.

Rule 8 stops at the chain because only phrases linked by joins share a level 0 in the text. Across chains, the round-trip check compares the motifs' measured pitch instead.

A repeat's body is checked as one copy. Its joins between copies are worked out from the start levels and never fail.

Checking that every syllable appears once and in order is also the round-trip check's job, because that needs the text.

## Grammar

```
line     = id " " dir ": " [join " "] items
dir      = "ltr" | "rtl"
join     = move | "="
items    = item (" " item)*
item     = note | fast | pause | move | repeat | motif
note     = [lyric ":"] ["~"] length
fast     = ">" length "{" bead (" " [move " "] bead)* "}"
bead     = [lyric ":"] "*"
pause    = "." length
move     = "!" | ["!"] ("^" | "v") [length]
repeat   = "(" items ")" "x" count [("^" | "v") [length]]
motif    = "#" label [("+" | "-") length] "[" items "]" | "[...]" "#" label
lyric    = syllable | "(" letters ")"
syllable = (letters | "<+" letters ">" | "<-" letters ">")+
```

`id` is one or more letters, digits, `_` and `-`, with no accents. `length`, `count` and `label` are whole numbers. A `(` that closes with `):` is a vowel label, and one that closes with `)x` is a repeat. `letters` is any run of letters and their combining marks, from both Coptic Unicode blocks or any other script.

Input aliases. Each is read as its canonical sign while the line is read token by token, never by replacing text across the whole line, so a lyric is never rewritten. `[...]` is read as a whole before any run of dots is considered, so its three dots are not a pause. The aliases are:

| Alias | Canonical |
| --- | --- |
| `↑` `↓` | `^` `v` |
| `↝` | `!` |
| `→` | `>` |
| `•` | `*` |
| `×` | `x` |
| `↗` `↘` | `^` `v` |
| `.` `..` and longer runs, with no digit after | `.2` `.4`; a run of n dots is `.{2n}` |
| `~` `~~` and longer runs, with no digit after | `~2` `~4`; a run of n tildes is `~{2n}`. A lyric may precede them: `lē:~`. |
| `[...]①` | `[...]#1` |
| `①` to `⑳` | `#1` to `#20` |

The `"[...]" "#" label` form in the motif row is input only; the writer never outputs it.

Parse-then-write tests use canonical text. One further test shows that input in hazzat signs normalises to the canonical form.

## In the JSON contracts

In `HymnString`, the id and direction are their own fields and `notation` holds the join, if any, and `items`. `format_version` is 1. `HymnString` and `ReviewRecord` both carry it, because both store notation as text and can outlive a format change.
