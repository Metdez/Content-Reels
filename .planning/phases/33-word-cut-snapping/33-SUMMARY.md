---
phase: 33
name: Adopt — Word-level Timing → Cut-snapping
status: complete
requirements: [WORD-01]
completed: 2026-06-30
---

# Phase 33 — Adopt: Word-level Timing → Cut-snapping — SUMMARY

**Outcome:** The editor trim now snaps to whisper's per-word boundaries (already in `transcript.json`, previously unused), with a clean segment-level fallback. **203 tests pass; ruff clean; verified live.**

## Change
- `app._clip_editor_payload` builds the trim `boundaries` set from every segment's `words[]` (`word.start`/`word.end`) plus segment start/end (fallback), tolerant of missing/garbage word entries. No new transcription work — pure consumption of existing data.

## Why this is the right scope
- Selection already lands on word boundaries by construction (a segment's start == its first word's start), so it needed no change. The new, user-visible capability is **editor trim precision** — a handle can now land on any word edge, not just a sentence edge.

## Verification
- `tests/test_word_snapping.py` (+2): boundaries include word timings (seeded job, `len > 40`); fall back to segment-only when `words` is stripped (`len <= 2*n_segs+2`).
- Live (seeded job): `/api/job/{id}/clip/1` boundaries = **137** word-level points (was ~18 segment-only); first few `[0.0, 0.3, 0.35, 0.65, 0.7, 1.0]` are word edges.
- `pytest -q` → 203 passed, coverage 92.4%; ruff clean.

## Research flag (carried)
whisper base.en word timings can drift ~±300ms; the segment fallback + the existing snap padding absorb it. Real-timing accuracy on a real video is exercised in Phase 36.

## Improvement criteria applied
**Correctness/UX** (tighter, word-accurate trims) + **feature adoption** (uses data already produced), zero new dependency or transcription cost.
