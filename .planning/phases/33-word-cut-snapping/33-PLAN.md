---
phase: 33
name: Adopt — Word-level Timing → Cut-snapping
wave: 1
requirements: [WORD-01]
autonomous: true
---

# Phase 33 — Adopt: Word-level Timing → Cut-snapping

**Goal:** Put whisper's already-emitted `segments[].words[]` to work — the editor trim can snap to word edges, not just sentence edges. Fallback to segment boundaries when word timing is absent/poor.

## Tasks
- `app._clip_editor_payload` snap-point set (`boundaries`) now includes every `word.start`/`word.end` (per segment), with segment start/end always included as fallback. Robust to missing/garbage word entries.
- Selection already lands on word boundaries by construction (a segment's start = its first word's start), so it needs no change; the new capability is editor trim precision.

## Verify (exit)
- `tests/test_word_snapping.py`: boundaries include word timings (seeded job), and fall back to segment-only when `words` stripped.
- Live: `/api/job/{seeded}/clip/1` boundaries count jumps from ~18 (segment) to word-level; trim handle can snap to a word.
- Full suite green; ruff clean.

## Research flag
whisper base.en word timings can be ~±300ms; the segment fallback + the existing
0.2–0.4s snap padding absorb drift. Real-timing accuracy is exercised in the Phase 36 real run.
