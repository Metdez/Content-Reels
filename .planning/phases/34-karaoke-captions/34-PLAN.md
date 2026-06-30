---
phase: 34
name: Adopt — Word-level Karaoke Captions
wave: 1
requirements: [CAPS-01, CAPS-02]
autonomous: true
---

# Phase 34 — Adopt: Word-level Karaoke Captions

## Blocker + decision (genuine tradeoff)
hyperframes requires **Node ≥22** (this env has **v20.20.2**) and a real Chrome (only `chromium-bidi` is present) — so it **cannot render here**, and provisioning Node 22 + headless Chrome is out of scope this session. Per "everything works", we deliver **word-level karaoke via the PNG-overlay pipeline that DOES work here** (Pillow + ffmpeg time-gated overlays, driven by `words[]`), and keep/extend the hyperframes composition (gated) with **PNG karaoke as the automatic fallback**.

## Tasks
- **CAPS-01** — new caption mode `karaoke`: build per-word highlight events from `segments[].words[]` (clip-relative), render a PNG per highlighted word (the phrase line with the current word in an accent color), composited by the existing time-gated `overlay` chain. Falls back to segment-level overlay when a segment lacks word timing.
- **CAPS-02** — gate the mode end-to-end (run-options dropdown + editor caption control gain "karaoke"); the hyperframes composition (`build_caption_composition`) updated to support word highlighting for Node≥22+Chrome boxes; on ANY hyperframes failure/unavailability the render falls back to PNG (existing guarantee preserved — now PNG-karaoke). Document the Node≥22+Chrome requirement.

## Verify (exit)
- Unit tests: word-event builder (per-word events + segment fallback), karaoke PNG generation (multiple PNGs), mode gating.
- **LIVE render + ffprobe**: render the seeded job's clip with `caption_mode="karaoke"` (real vendored ffmpeg on the seeded source.mp4) → valid h264 + audio output; confirm more overlay PNGs than segment mode. Prove hyperframes→PNG fallback path.
- Full `pytest -q` green; ruff clean.

## Note
Live karaoke renders via PNG here; the hyperframes variant is code-complete + gated but unrenderable in this env (Node 20 / no Chrome) — documented, with PNG as the working path + fallback.
