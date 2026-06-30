---
phase: 34
name: Adopt — Word-level Karaoke Captions
status: complete
requirements: [CAPS-01, CAPS-02]
completed: 2026-06-30
---

# Phase 34 — Word-level Karaoke Captions — SUMMARY

**Outcome:** A `karaoke` caption mode renders word-by-word highlighting driven by whisper's `words[]`, delivered through the PNG-overlay pipeline that works in this environment, with the hyperframes path gated + an automatic PNG-karaoke fallback. **211 tests pass; ruff clean; live ffprobe-validated; fallback proven end-to-end.**

## The constraint (documented)
hyperframes needs **Node ≥22** + Chrome; this env has **Node v20.20.2** + no Chrome → it can't render here. Per "everything works", karaoke is delivered via PNG overlays (Pillow + ffmpeg time-gated `overlay`), which renders + validates here. The hyperframes composition is code-complete + gated for capable boxes, with PNG-karaoke as the fallback.

## Changes
- **CAPS-01** — `captions.clip_word_events()` emits one event per word `{start,end,text,highlight}` (clip-relative, word index in its display line; segment-level fallback when no word timing). `render_caption_png(..., highlight=)` draws the highlighted word in `#FFE600`; `render_caption_pngs` passes it through (non-karaoke path byte-identical). `render.py` wires `caption_mode="karaoke"` through the same overlay chain.
- **CAPS-02** — mode gated end-to-end: `_clip_editor_payload` accepts `"karaoke"`; `job.html` run-options + `editor.html` caption control expose it. `build_caption_composition` (hyperframes) highlights the current word for Node≥22+Chrome boxes; on ANY hyperframes failure/unavailability the render falls back to PNG-karaoke (highlighting preserved, `captions_used="karaoke"`). Default `overlay`/`none` behavior unchanged.

## Verification
- **Live render + ffprobe (seeded clip 1, real ffmpeg):** `clip_word_events=40` vs 5 segment events → 40 highlighted PNGs; output **h264 1080×1920 + aac, 14.83s** — independently ffprobe-confirmed.
- **Fallback proven live:** `hyperframes_available()` True (bin vendored) → karaoke entered the hyperframes branch → failed at runtime (`WinError 193`, Node 20/no Chrome) → fell back to PNG-karaoke, render succeeded with highlighting intact.
- Tests (+ ~9): `clip_word_events` (per-word/highlight/wrap/segment-fallback), karaoke PNG accent pixel present (plain path none), hyperframes karaoke composition, `_clip_editor_payload` accepts karaoke, karaoke yields more overlay events than overlay.
- `pytest -q` → 211 passed, coverage 92.4%; ruff clean.

## Known limitation (opt-in tradeoff — flagged for Phase 36 docs)
PNG-karaoke uses one overlay input per word, so a long/wordy clip's filter_complex is large and encodes slowly (the 14.8s/40-word test took minutes at ~0.024×). Acceptable because: karaoke is **opt-in** (default `overlay` is fast + unaffected) and produces valid output. Future optimization: coalesce words into fewer composited inputs. Documented, not optimized this phase (optimizing risks the working path).

## Improvement criteria applied
**Feature adoption** (karaoke, the hyperframes/whisper-words differentiator) + **Reliability** ("must not break": PNG fallback intact, default mode untouched) + **Correctness** (word-accurate highlight from real word timing). The perf cost is a stated, bounded, opt-in tradeoff.
