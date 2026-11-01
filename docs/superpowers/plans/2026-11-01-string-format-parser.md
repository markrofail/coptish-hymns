# String format: owner's revisions, parser, writer, validator

**Spec:** `hymnstring/notation/SPEC.md`, once Task 1 has revised it. After Task 1 it is the binding authority for Tasks 2 and 3. CONTEXT.md and PLAN.md are the design record; read them only where a task points you to them.

**Milestone:** PLAN.md Phase 0 item 3. Done when every rule has a canonical example that survives parse-then-write unchanged, one test shows hazzat-sign input normalises to the canonical form, and the owner has approved the format. The owner approved it subject to these revisions being in SPEC.md with tests.

**Not in this plan:** the renderer, the synthesiser, any audio code, or building the aligner. Nothing here installs torch or torchaudio.

## Global Constraints

- Work on the `phase-0` branch in `/Users/mark/workplace/coptish/coptish-string-notation`. Never touch `main`.
- Python 3.12 in `.venv`. Run tests with `.venv/bin/python -m pytest`. The hook `rtk` rewrites some shell commands; prefix `rtk proxy` if a command is refused or its output is filtered.
- Add no dependencies. The notation package uses the standard library only.
- `hymnstring/notation/` must never import `hymnstring.contracts`. Contracts import notation, not the reverse.
- Hazzat steps and lengths are relative. Nothing may introduce semitones, absolute pitches, seconds or BPM into the notation.
- Follow TDD: watch each test fail before writing the code. Expected values are hand-derived literals, never computed by the code under test.
- Match the surrounding code: short module docstrings, comment density as in `hymnstring/harness.py` and `hymnstring/contracts/`, frozen dataclasses or contracts, no speculative options.
- End every commit message with: `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`
- Docs are written in plain, direct English, matching the existing voice of SPEC.md and CONTEXT.md.

## Task 1: Apply the owner's decisions to the docs, contracts and graph test

**Files:** `hymnstring/notation/SPEC.md`, `CONTEXT.md`, `PLAN.md`, `CLAUDE.md`, `pyproject.toml`, `hymnstring/contracts/text.py`, `hymnstring/contracts/inputs.py`, `fixtures/contracts/*.json`, `tests/test_contracts.py`, `tests/test_graph.py`.

Read `hymnstring/notation/SPEC.md` in full first. Keep its structure and voice. Change what follows, and make every section agree with it, including "The idea", the token table, the rule examples, the demo table, the validity rules, the grammar and the alias table.

### SPEC.md: status line

Change the status to: format version 1, approved by the owner on 2026-11-01.

### SPEC.md: repeats hold one copy

This replaces the old rule that repeats are written out in full in the text, so rewrite rule 5 of "The idea". Every bead in the drawing no longer has its own token. Brackets still only label notes, and a repeat expands to a flat list of notes.

- Canonical forms: `(body)xN`, `(body)xN^`, `(body)xNv`, `(body)xN^K`, `(body)xNvK`.
- `body` holds one copy. `N` is the total number of copies, at least 2. `K` is levels per copy, at least 1. A `K` of 1 is left out.
- Copy `i` (counting from 0) starts at `start + i * delta`, where delta is 0 for `xN`, `+K` for `^`, `-K` for `v`.
- Between consecutive copies, the join is a smooth move of whatever size the start levels require. If no level change is needed there is no move, so the next copy's first note is a re-sung note.
- The renderer writes the copies out in full, under a bracket. Lyric labels (syllables and vowel labels) go on the first copy only.
- A repeat whose copies carry different syllables can't use this form. Write the notes out; a motif can label them.
- Hazzat signs: `(lou:1)×3↗`, `(lou:1)×3↘`, `(lou:1)×3↗2`.
- Examples to include: `(1)x3` levels 0,0,0. `(lou:1)x3^` levels 0,1,2. `(1)x3v2` levels 0,-2,-4. `(1 ^ 1)x2` levels 0,1,0,1 with a smooth `v` join. `(1 ^ 1)x3^` levels 0,1,1,2,2,3 with no move between copies.

The demo phrase becomes:

```
p1 ltr: #1[A:2 ^ 1 v 1] ^ lē:~2 .2 v (lou:1)x3^ >1{i:*} a:2 !v2 #1[(a):2 ^ 1 v 1] v 4
```

Its row 6 is `v (lou:1)x3^` in canonical form and `↓ (lou:1)×3↗` in hazzat signs. Rows 4 and 5 show hazzat signs `↑ lē:~` and `.`. Levels, lengths, 13 beads and 22 units are unchanged. Note that the text now has fewer tokens than beads.

### SPEC.md: bare `!`

Add a bare `!` (hazzat sign `↝`): a quick move on to the next notes with no change of level, drawn as a short tick across the string. `!^`, `!v` and their sized forms are unchanged. Update the "Moves" section: `!` still always means abrupt, whatever the size, and now that includes size zero.

### SPEC.md: phrase joins

Add a section on joins.

- A phrase may begin with one optional join, before its first note: a move from the previous phrase's last note, for example `p2 ltr: v2 1 ^ 2`. Any move form is allowed (`^`, `v2`, `!`, `!v2`).
- Ruling by the controller, not the owner: `=` is a join meaning "same level as the previous phrase's last note". A chain needs a way to say this, and sizes below 1 are invalid. `=` is valid only as a join, and has no hazzat sign.
- After a trailing pause, the previous level is the level the pause held.
- The first phrase of a hymn can't have a join.
- A join is followed by a note, a fast group, or a bracket that starts with one, never by a pause or another move.
- A **chain** is a run of phrases linked by joins. A phrase with no join starts a new chain. Inside a chain levels can be compared, so motifs are checked strictly. Across chains the text has no shared level, so motifs are checked by shape only and the round-trip check compares their measured pitch. When every phrase after the first has a join, the whole hymn is one chain and motifs are checked strictly everywhere.
- Each phrase is still drawn with its own lowest note as level 0. Chains exist so levels can be compared.
- In the JSON `HymnString`, `notation` holds the join and the items.

### SPEC.md: strict motifs

Replace the old "within one phrase" rule. Within a chain, all plain occurrences of a motif must start on the same level, and an occurrence `#1+n` must start `n` levels from the plain occurrences in that chain, if there are any. "Same shape" is compared after expanding repeats, so `#1[(1)x3 ^ 2]` and `#1[1 1 1 ^ 2]` have the same shape. A motif inside a level-changing repeat occurs at a new level in each copy, so a strict motif there is invalid. The first occurrence of a label in the hymn must be plain.

### SPEC.md: more aliases, and extensions

Hazzat-sign column and alias table:

- `.` = `.2` and `..` = `.4`. A run of n dots is `.{2n}`.
- `~` = `~2` and `~~` = `~4`. A run of n tildes is `~{2n}`. A lyric may precede them: `lē:~`.
- A later `[...]①` (literally three dots, label after the bracket; `[...]#1` also works) with no notes copies the first occurrence's shape, without its lyrics. It is resolved when the hymn is parsed, across phrases, and the writer outputs the full canonical occurrence such as `#1[2 ^ 1 v 1]`. With no earlier occurrence it is an error. There is no shifted form of it.
- Keep the existing aliases: `↑ ↓ ↝ → • × ↗ ↘ ①-⑳`.

Add a short "Extensions" section listing what hazzat can't express: shifted motifs; half-length pauses and vibratos (`.1`, `~1`, and any odd length, which have no sign in hazzat's whole-note counts); and move sizes above 1, which only strings from audio use.

### SPEC.md: validity rules

Rewrite the list so it matches the above: join rules; repeat count at least 2; move sizes at least 1 (bare `!` has no size); repeat and motif edges; the chain-based motif rule. Delete the old rule that repeat copies must divide evenly, because a repeat now holds one copy. Update the grammar:

```
line     = id " " dir ": " [join " "] items
join     = move | "="
item     = note | fast | pause | move | repeat | motif
move     = "!" | ["!"] ("^" | "v") [length]
repeat   = "(" items ")" "x" count [("^" | "v") [length]]
```

The other grammar rows stay. Move rule 8's old wording about phrases to chains. Rule examples: replace the repeat row with `(1)x3 ^ (1)x3^ (1)x3v` and add rows for `!` (`2 ! 2`) and a join (`p2 ltr: v2 1 ^ 2`, read after a first phrase). Keep every example valid under the rules.

### CONTEXT.md

- Section 2: on the ↝ row add that with no change of level it is a short tick across the string. On the repeat row add that lyric labels go on the first copy only.
- Section 4: **Note onsets** must not use the pulse unit (for example in breath thresholds), because pulse runs after onsets and that would make a cycle. **Lyric aligner**: the catch-all token is torchaudio's star token.
- Section 6, Lyric aligner row: replace with torchaudio 2.2.2's `MMS_FA` pipeline with `torchaudio.functional.forced_align` and its star token. Notes: it has Intel Mac builds for Python 3.10 to 3.12 and pins torch 2.2.2; it stays behind the aligner node's interface because torchaudio removed this API in 2.9; the weights are CC-BY-NC 4.0, non-commercial. Drop the `ctc-forced-aligner` link.

### PLAN.md

- Replace the header note "Edited here after export..." with: "This repo's PLAN.md is now the source of truth; the Claude doc stays as the original version."
- Phase 1 item 2: the romanised form uses `MMS_FA`'s alphabet exactly: lowercase a-z and apostrophe.
- Phase 2 item 3: name the aligner as above, keeping its test and Done-when text.
- Phase 2 item 4: onsets must not use the pulse unit.
- Risks table: add a row: torchaudio removed forced alignment in 2.9; effect: upgrading breaks the aligner; mitigation: pin 2.2.2 and keep it behind the node's interface.

### CLAUDE.md

- Replace the bullet "Use Python 3.11 or later in a virtual environment, with pinned dependencies." with one saying to use Python 3.11 or 3.12 in a virtual environment, with pinned dependencies, and that Python must stay at 3.12 or earlier on this Mac because torch 2.2.2 and torchaudio 2.2.2 have no Intel Mac wheels for 3.13.
- Replace the gotcha about `ctc-forced-aligner` with: torchaudio's forced-alignment API was removed in torchaudio 2.9, so use torchaudio 2.2.2's `MMS_FA` pipeline with `torchaudio.functional.forced_align` and its star token, behind the aligner node's interface.

### pyproject.toml

Set `requires-python = ">=3.11,<3.13"`.

### Contracts and fixtures

- `SyllableSound.romanised` must match `MMS_FA`'s alphabet exactly: lowercase a-z and apostrophe, at least one character. Add a named type in `hymnstring/contracts/text.py`. Test rows in `BROKEN` in `tests/test_contracts.py`: a macron (`lē`), a capital (`A`), a space (`a b`). Add one test that an apostrophe is accepted.
- In every fixture holding `sounds`, change the romanised form `lē` to `le`. `sounds` keeps `["l", "ē"]`.
- In every fixture holding the demo notation, change it to `#1[ⲁ:2 ^ 1 v 1] ^ ⲗⲏ:~2 .2 v (ⲗⲟⲩ:1)x3^ >1{ⲓ:*} ⲁ:2 !v2 #1[(ⲁ):2 ^ 1 v 1] v 4`. These are JSON files with composite copies: `hymn_string.json`, `library_entry.json`, `miner_input.json`, `interpreter_input.json`, `round_trip_input.json`, `render_input.json`. Edit with a small throwaway script or by hand, and keep the 2-space JSON layout with `ensure_ascii=False`.
- `OnsetsInput` docstring in `hymnstring/contracts/inputs.py`: say it must not take the pulse unit, because pulse runs after onsets.

### Graph test

Add to `tests/test_graph.py` a test that the drawn graph is acyclic apart from its two deliberate feedback loops: the retry `RT -> HI` and the cantor's fixes `CR -> HL`. Use `graphlib.TopologicalSorter` over `drawn_edges()` minus those two edges. Watch it fail first by temporarily drawing a `PU --> ON` edge in CONTEXT.md, confirm `CycleError` fires, then restore the file. Report that you did.

## Task 2: Model, parser and writer

**Files:** create `hymnstring/notation/__init__.py`, `hymnstring/notation/model.py`, `hymnstring/notation/parser.py`, `hymnstring/notation/writer.py`, `tests/test_notation_parser.py`.

Read `hymnstring/notation/SPEC.md` in full. It is binding. Implement its grammar and alias table.

`model.py` holds frozen dataclasses:

- `Letters(text: str, mark: Literal["plain", "added", "silent"])`
- `Syllable(parts: tuple[Letters, ...])`, `Vowel(letters: str)`
- `Note(length: int, vibrato: bool = False, lyric: Syllable | Vowel | None = None)`
- `Pause(length: int)`
- `Move(abrupt: bool, change: int)`: signed levels. Bare `!` is `Move(True, 0)`. A smooth move never has `change == 0`.
- `SameLevel()`: the `=` join
- `Bead(lyric: Syllable | Vowel | None = None)`
- `Fast(length: int, items: tuple[Bead | Move, ...])`
- `Repeat(items: tuple[Item, ...], count: int, step: int = 0)`: `step` is signed levels per copy
- `Motif(label: int, shift: int, items: tuple[Item, ...])`
- `Phrase(phrase_id: str, direction: Literal["ltr", "rtl"], join: Move | SameLevel | None, items: tuple[Item, ...])`
- `Hymn(phrases: tuple[Phrase, ...])`
- `Item = Note | Fast | Pause | Move | Repeat | Motif`

Public API, re-exported from `hymnstring.notation`:

- `class NotationError(ValueError)`: its message names the problem and where.
- `parse_hymn(text: str) -> Hymn`: one line per phrase. Blank lines aren't allowed. Resolves `[...]①` in order across phrases.
- `parse_line(line: str) -> Phrase`: one phrase alone. `[...]①` resolves only against occurrences earlier in that line.
- `write_hymn(hymn: Hymn) -> str`, `write_line(phrase: Phrase) -> str`: canonical text, joined by `\n` with no trailing newline.

The parser raises `NotationError` for anything the grammar rejects: unknown tokens; a length, size, count or label below 1; a shift of 0; unbalanced or unclosed brackets; `=` anywhere but the join position; `*` outside a fast group; anything but `*` and moves inside a fast group; a lyric that isn't NFC or holds anything but letters, combining marks and letter marks; a `[...]` with no earlier occurrence. Structural rules that need levels or neighbours (phrase edges, move followers, bracket edges, repeat count below 2, motif rules, join on the first phrase) belong to Task 3's validator, so `(1)x1`, `1 ^`, `^ ^ 1`, and `(^ 1)x2` must parse.

A leading move or `=` on a phrase goes in `Phrase.join`, not in `items`.

Do aliases inside the tokeniser, not by blind text replacement, so a lyric is never rewritten. A lyric is told from a move by its `:`. `v:2` is a note with the lyric "v"; `v2` is a move. Letters in `letters` may be from any script.

Tests in `tests/test_notation_parser.py`, all table-driven with hand-written literals:

- Canonical text survives parse-then-write unchanged. Harvest every example from the "One example for each rule" table in `SPEC.md` (the backticked cell of each row), adding `p1 ltr: ` where the example has no prefix, and also the demo line. Assert the harvest found at least 14 examples, so a broken harvest can't pass silently.
- Parsing yields the expected model for a table of small cases, covering each model type, including `(lou:1)x3^` as `Repeat((Note(1, lyric=...),), 3, 1)`, `(1)x3v2` with `step=-2`, bare `!` as `Move(True, 0)`, `#1-2[1]` with `shift=-2`, and a join.
- One alias test, table-driven, for input in hazzat signs. Each row is an input and its literal canonical output after `write_hymn(parse_hymn(input))`. Rows must include the whole demo in hazzat signs, `①[A:2 ↑ 1 ↓ 1] ↑ lē:~ . ↓ (lou:1)×3↗ →1{i:•} a:2 ↝↓2 ①[(a):2 ↑ 1 ↓ 1] ↓ 4`; `2 .. 2` to `2 .4 2`; `~~` to `~4`; `2 ↝ 2` to `2 ! 2`; `(1)×2↘2` to `(1)x2v2`; `^1` and `x3^1` and `!v1` dropping their 1; and `[...]①` copying shape without lyrics, both within a phrase and across phrases.
- Rejections: a table of inputs raising `NotationError`, one for each parser rule above.
- Lyric marks: `ⲧ<+ⲉ>ⲛ:2` and `<-ϩ>ⲁ:2` parse to the right `Letters`, and a jinkim (`ⲛ̀`) and both Coptic blocks (`ϣ`, `ⲁ`) are accepted.

## Task 3: Flatten, validator and contract wiring

**Files:** create `hymnstring/notation/flatten.py`, `hymnstring/notation/validator.py`, `tests/test_notation_flatten.py`, `tests/test_notation_validator.py`; modify `hymnstring/notation/__init__.py`, `hymnstring/contracts/judgement.py`, `tests/test_contracts.py`.

Read `hymnstring/notation/SPEC.md` in full. It is binding. The model and parser from Task 2 exist.

### `flatten.py`

Expands a sequence of items into a flat list of events, tracking levels. Public: `flatten(items, start_level=0) -> Flat`, where `Flat` has `events`, `end_level` and `motifs`.

- Events: `FlatNote(level: int, length: Fraction, kind: Literal["note", "vibrato", "fast"], lyric, move: Move | None)` and `FlatPause(level: int, length: Fraction)`. `move` is the move into this note, including a repeat's join, or `None` if there is none. Lengths use `fractions.Fraction`, because a fast group splits its length evenly.
- A repeat expands per SPEC.md: copy `i` starts at `start + i * step`; a join between copies is `Move(False, needed)`, or no move when `needed` is 0; lyrics stay on the first copy only.
- `motifs`: one `MotifUse(label, shift, start_level, shape)` per occurrence in order, including one per copy when a motif sits inside a repeat. `shape` is the tuple of `(move, kind, length)` per event of the occurrence after expanding it, with the first event's move left out and pauses included. Lyrics and levels aren't part of it.

Tests, hand-derived literals: the demo gives levels `[1, 2, 1, 2, None, 1, 2, 3, 3, 3, 1, 2, 1, 0]` once shifted so the lowest note is 0 (`None` for the pause), lengths `[2, 1, 1, 2, 2, 1, 1, 1, 1, 2, 2, 1, 1, 4]`, 13 notes and 22 units in total. `(lou:1)x3^` levels 0,1,2 with the lyric only on the first note. `(1)x3` levels 0,0,0 with no moves. `(1)x3v2` levels 0,-2,-4. `(1 ^ 1)x2` levels 0,1,0,1 with a smooth join of -1 into the third note. `(1 ^ 1)x3^` levels 0,1,1,2,2,3 with no move into the third and fifth notes. `(1 .1)x2^` gives note 0, pause at 0, note 1, pause at 1. `>2{* ^ * v *}` levels 0,1,0, each of length 2/3. `1 ! 1` keeps the level, with `Move(True, 0)` into the second note.

### `validator.py`

`validate(hymn: Hymn) -> list[Problem]`, empty when valid. `Problem(rule: str, phrase_id: str, message: str)`. Tests assert `rule` and `phrase_id`, never message wording. Rule ids:

- `phrase_start`: a phrase's first item (after any join) is a pause or a move
- `phrase_end`: a phrase ends on a move
- `move_follower`: a move followed by another move or a pause, including the join
- `bracket_edge`: a repeat or motif starts with a pause or a move, or ends on a move
- `repeat_count`: a repeat count below 2
- `first_join`: a join on the hymn's first phrase
- `motif_order`: a shifted motif before the label's first plain occurrence in the hymn
- `motif_shape`: an occurrence's shape differs from the label's first occurrence
- `motif_level`: within a chain, plain occurrences start on different levels, or `#n+s` isn't `s` levels from them

Chains: a phrase with a join continues the previous phrase's chain at the previous phrase's `end_level`, plus the join's change (0 for `=` or bare `!`). A phrase with no join starts a new chain.

Table-driven tests, each a literal hymn and its literal expected `(rule, phrase_id)` list:

- Valid: the demo; `#1[2 ^ 1] v 2 #1[ⲡⲉ:2 ^ 1]`; `#1[2 ^ 1] #1+1[2 ^ 1] v3 #1-1[2 ^ 1]`; `(#1[1 ^ 1])x2`; `#1[(1)x3 ^ 2] v #1[1 1 1 ^ 2]`; `1 ! 1`.
- `#1[2 ^ 1] v #1[2 ^ 2]`: `motif_shape`. `#1[2 ^ 1] #1[2 ^ 1]`: `motif_level`. `#1[2 ^ 1] v #1+1[2 ^ 1]`: `motif_level`. `(#1[1 ^ 1])x2^`: `motif_level`. `#1+1[2] #1[2]`: `motif_order`.
- `p1 ltr: #1[2 ^ 1]` then `p2 ltr: 2 #1[2 ^ 1]`: valid, shape only across chains. With `p2 ltr: = #1[2 ^ 1]`: `motif_level` on p2. With `p2 ltr: v #1[2 ^ 1]`: valid. With `p2 ltr: v2 #1[2 ^ 1]`: `motif_level` on p2. With `p2 ltr: ! #1[2 ^ 1]`: `motif_level` on p2.
- Four phrases where p3 has no join: a motif in p1 and in p4 at different levels is valid.
- `p1 ltr: ^ 1`: `first_join`. `.2 1`: `phrase_start`. `1 ^`: `phrase_end`. `p1 ltr: 1` then `p2 ltr: = .2 1`: `phrase_start` on p2. `1 ^ ^ 1`, `1 ^ .2 1`, `1 ! ^ 1`: `move_follower`. `(1)x1`: `repeat_count`. `(^ 1)x2`, `(1 ^)x2`, `(.2 1)x2`, `#1[^ 1]`, `#1[1 ^]`: `bracket_edge`.

### Contract wiring

In `hymnstring/contracts/judgement.py`:

- `HymnString`: after its existing checks, build the text form from its phrases (`f"{phrase_id} {direction}: {notation}"`, one per line), parse it, require that `write_hymn` gives back the same text (canonical only), and require that `validate` finds no problems. Raise `ValueError` naming the problems.
- `ReviewRecord`: `before` and `after` must each be canonical notation for one phrase, by the same parse-then-write check, using `phrase_id` and `ltr`. They aren't validated as a hymn.

Add `BROKEN` rows to `tests/test_contracts.py`: a `HymnString` with alias signs in its notation (`1 ↑ 2`), with unparsable notation, and with a structural problem (`1 ^`); a `ReviewRecord` whose `after` isn't canonical. Update `PhraseString`'s docstring if it needs it. `LibraryEntry` needs no change.
