# Coptic hymn to string notation

This repo builds an agent pipeline that turns a recording of a Coptic hymn, plus its Unicode Coptic text, into string notation: a continuous-line form of hazzat, the notation Coptic cantors use.

The design was made in a Claude chat you can't see. Read CONTEXT.md (design decisions) and PLAN.md (build plan) before writing any code; together they are the full record. If something in them is ambiguous, ask me rather than guessing.

## How to work

- Follow PLAN.md in order. Phases 1 and 2 may run in parallel once Phase 0's gate passes.
- Take one milestone at a time. For each: define or extend its data contract, write its tests, make them pass, run the whole suite, then stop and report against the milestone's "Done when", with the actual numbers.
- Never call a milestone done while a criterion is unmet. Say what is missing and propose a fix.
- Stop and ask me at every phase gate, and before you:
  - change a data contract that another node already uses;
  - add a model or dependency with a new licence;
  - need an input from me (see "What I need from you" in PLAN.md).
- Each node is a module that runs on its own from the command line: JSON in, JSON out.
- All LLM calls go through one client wrapper that records responses, keyed by a hash of the model, prompt and inputs. Tests run in replay mode and never call the API.
- Keep commits small: one milestone or less each.

## This Mac versus the plan

- PLAN.md was drafted by a Claude working in a cloud workspace where Hugging Face was blocked. Here it isn't, so use the "On your computer" column of "Where each part runs": RMVPE and the MMS aligner. Keep the lighter fallbacks only as optional alternatives behind one config setting.
- In PLAN.md, "I" is the Claude that drafted it and "you" is me, the owner of this repo.
- This Mac is an Intel i7-9750H, not Apple Silicon: PyTorch is capped at 2.2.2, and there is no MPS or CoreML, so everything runs on CPU. Prefer ONNX routes. Install ffmpeg with Homebrew.
- Version 1 skips separation. It is one node with three backends chosen by a setting: `bypass` (the default for now), `demucs` and `roformer`. When bypassed, pitch and pulse run on the full mix.
- When separation is needed, try `audio-separator` 0.24.1 on PyTorch 2.2.2 first. If it fails, use Demucs 4.1.0. As a last resort, separate on another machine and cache the stems.
- Use Python 3.11 or later in a virtual environment, with pinned dependencies.
- Keep model weights in a cache outside the repo. Never commit audio, weights or API keys, and keep test fixtures small.
- The two agents read `ANTHROPIC_API_KEY` from the environment, and the model name lives in one config value.

## Gotchas

- Coptic letters span two Unicode blocks (CONTEXT.md, section 5). Normalise before matching.
- Hazzat steps and lengths are relative. Never quantise to semitones, absolute pitches or BPM.
- torchaudio's forced-alignment API was removed in torchaudio 2.9; use `ctc-forced-aligner`.
- The MMS aligner weights are licensed for non-commercial use only (CC-BY-NC 4.0).

## Suggested layout

```
hymnstring/
  contracts/   typed schemas for every edge in the graph
  notation/    string format: parser, writer, validator, renderer
  synth/       string to audio, plus ground-truth files
  nodes/       one module per graph node
  llm/         client wrapper with record and replay
  library/     hymn library store
tests/
fixtures/
reference/     string_demo.svg, the agreed look of the demo phrase
```

## First task

Phase 0, items 1 and 2 (harness and contracts). Then item 3: draft the string format as a short spec, with an example for every rule in CONTEXT.md section 2 and the demo phrase from section 3 written in it. Stop for my approval before writing the parser.
