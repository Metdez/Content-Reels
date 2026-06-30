---
gsd_state_version: 1.0
milestone: v6
milestone_name: Full Quality Pass — Test, Harden, Improve, Adopt
status: complete
last_updated: "2026-06-30T15:53:15.536Z"
last_activity: 2026-06-30
progress:
  total_phases: 14
  completed_phases: 14
  total_plans: 14
  completed_plans: 14
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-29)

**Core value:** Drop in one video and get back several genuinely good, caption-burned clips in 9:16/1:1/16:9 — locally, no cloud, no per-token API cost.
**Current focus:** Milestone v6 — Full Quality Pass: Test, Harden, Improve, Adopt (Phases 23–36). Senior-engineer ownership pass: exhaustive automated + Playwright coverage, fix every defect surfaced, improve against an explicit "better" standard, adopt worthwhile repo features. v1.0–v5.1 complete and verified live.

## Current Position

Phase: 36 of 36 COMPLETE — **MILESTONE v6 COMPLETE (14/14)**.
Plan: —
Status: Phase 36 (final verification & docs) shipped — README v6 update; "better" criteria + the karaoke perf tradeoff documented; self-audit clean (41/41 requirements mapped+delivered, 14/14 phases with PLAN+SUMMARY). Final gates: unit 211 pass (~92.4% cov, from 64.2%), e2e UI 34 pass, crop parity pass, ruff clean. All 8 discovery bugs + 1px crop drift fixed. No known broken functionality.
Last activity: 2026-06-30 — Phase 36 complete (DONE-01); milestone v6 complete

### v6 progress

- P23 ✓ Test Harness & CI: pytest-cov (64.2% baseline), tests/conftest.py (`client` TestClient + `seed_job`/`seeded_job`), tests/test_harness.py (+6 HTTP tests), scripts/seed_fixture.py (real-media seed, browser-verified), [tool.ruff] clean, .github/workflows/test.yml, Makefile lint/cov/e2e-seed.
- P24 ✓ Backend Unit Coverage: +92 tests (6 new files, written in parallel). Coverage 64.2%→89.2% (config/logging_setup 100%, cli 97.9, captions 98.9, render 98.6, select 95.7, transcribe 92.9). app.py 74.5% → P25; hwaccel 60% (real probe is hardware).

### Bugs found in P24 (deferred to fix phases — DO NOT lose)

1. ~~**REL (P26):** `rerender_one`/`render_job` non-atomic read-modify-write of `render.json`~~ — **FIXED in P26** (atomic_write_text + read_json + per-job locked upsert).
2. ~~**VAL-02 (P28):** `run_claude` leaks raw `JSONDecodeError`~~ — **FIXED in P28** (guarded parse → clear RuntimeError + retry).
3. ~~**VAL-02 (P28):** no retry — one bad chunk aborts whole selection~~ — **FIXED in P28** (retry×3 + per-chunk skip).
4. ~~**P28 minor:** `select.py` `proc.stderr[:500]` None-risk~~ — **FIXED in P28** (`(proc.stderr or "")`).
5. **P30 note:** `stream_run` swallows `on_line` exceptions + raises `CalledProcessError` with no captured output (`logging_setup.py:123-124, 131`) — buggy progress parser/error detail invisible.
6. ~~**P27:** `/upload` reverts `ingest` stage to `pending`~~ — **FIXED in P27** (save metadata first, then mark ingest done).
7. ~~**P28:** VAL-05 `/media` serves `job.json`/`transcript.json` verbatim~~ — **FIXED in P28** (MediaFiles allowlist).
8. **P28 minor (left, harmless):** dead empty-filename 400 guard (Starlette returns 422 first) (`app.py:319-320`) — documented, no-op, not worth changing.
9. **Note (by design):** traversal name neutralized to basename (303), not rejected 400 (`app.py:42-49`).

### Verified live (v5.1, Windows 11, real NVENC + Playwright)

- P20 poll-in-place: editor 600ms re-render poll + job-page 2.5s clips poll now patch the DOM in place; finished `<video>` elements are created once and never refetched, so they stop spinning forever; active aspect tab preserved across reconcile.
- P21 Quick-crop parity + visibility: modal gained per-aspect zoom + Position-Y + Position-X with a live output-preview canvas (reuses `computeCrop`/`drawBox`/`drawOut`), seeded from saved transforms. Re-render switched from the old blocking `/reframe` to non-blocking `/edit` + `/rerender-status` poll: progress bar + %, per-aspect queued/rendering/done rows, and a live `/api/job/{id}/log` tail in the modal. Live test: set zoom 2.0 / x +26% / y +16% → 9:16 rendered then 1:1,16:9 promoted from queued → 0→100% → all done ✓ → card refreshed in place; transforms persisted to edit.json. Fixed two bugs found in testing: outputs lagging the done-transition, and a reconcile-sig clear that rebuilt an un-cache-busted `<video>` (now a shared-token cache-bust on stable paths).
- P22 direct manipulation: scroll-wheel zooms (`zoom*exp(-deltaY*0.0016)`, clamped 1–3×) and dragging pans (grab-the-image mapping) on the modal preview, sliders kept synced. Live: wheel 1→1.60×, drag +60/+40px → x=−14% y=−36% with correct direction + slider sync.

### Verified live (v5, Windows 11, real ffmpeg/NVENC + browser)

- P19 edit-flow polish + verification: added an always-visible header state pill (Idle → ● Unsaved changes → ⟳ Rendering N/3 → ✓ Rendered / ⚠ Render failed) driven by one `updateFlowPill()` state function; render failures now surface a readable message ("⚠ Re-render failed — <msg>. Your clip's previous version is untouched.") instead of a silent hang (unit-tested via a forced exception → tracker `status:error`, aspect `error`). Fixed a pre-existing ordering bug where the trim-drag handler called `markDirty()` before setting `dirtyClip` (mislabeled a trim as "Framing changed"). Full live walkthrough on EnlayeParis clip 1: Idle→Unsaved→Rendering→Rendered, ffprobe confirms all 3 re-rendered ratios valid (9:16=1080×1920, 1:1=1080×1080, 16:9=1920×1080, all h264+aac, 16.84s reflecting the new trim). 57 tests pass.

- P18 direct-manipulation framing + magnifier: on the output preview, scroll-wheel zooms the crop (`exp(-deltaY)` smoothing, clamped 1–3×) and dragging pans it with a grab-the-image mapping (`x -= 2·ddx·cw/(fw·sx)`), only mutating `TF.{zoom,x,y}` so the existing sliders stay a live fallback. Verified live: wheel 1→1.62×, drag set x=0.14/y=0.34 with correct direction + slider sync. **Pixel-parity confirmed** — JS `computeCrop(1920,1080,'9:16',0.14,1.6,0.34)`=`{x:878,y:271,w:380,h:674}` equals Python `compute_crop(...)`=`(w380,h674,x878,y271)`. A `🔍 Inspect` button cycles MAG 1→1.5→2× (CAP=420·MAG, stage goes single-column) to enlarge the preview for detail without touching the output transform (verified: x/y/zoom unchanged after magnify). 56 tests pass.

- P17 background re-render: `save_clip_edit` now enqueues onto a per-clip worker thread (`_RERENDER` tracker + `_enqueue_rerender` + `_rerender_worker`) and returns immediately — the editor never blocks. New `GET /clip/{idx}/rerender-status` exposes per-aspect state; `editor.html` polls it (600ms), shows an overall bar + per-aspect cards (queued/rendering/done/error) and drops each rendered output `<video>` in place as its ratio finishes. Aspects encode serially (1 NVENC engine): one "rendering", rest "queued", promoted on each completion. An edit made mid-render queues (single in-flight + 1 pending slot) and runs after — verified live: all-3 render showed `9:16 rendering · 1:1,16:9 queued` → progressed one-by-one; a second edit fired mid-flight set `queued:true` and ran after gen-1, nothing lost. `rerender_one` gained an `on_aspect_done` passthrough. 56 tests pass (+queue regression test).

### Verified live (v4, Windows 11, RTX 5060 + real binaries + ffprobe)

- P13 hwaccel core: select_encoder() probes encoders once + caches; picks nvenc on this machine; build_render_cmd emits the GPU tail on all paths; a real 9:16 render = valid 1080×1920 h264 + aac + faststart; CM_FORCE_CPU=1 → x264 parity; _run_encode auto-retries on libx264 if a GPU encode fails (unit-tested). 60s clip: NVENC 7.85s vs x264 10.68s = 1.36×.
- P14 Windows enablement: setup.ps1 pins NVENC-capable ffmpeg 7.1 (master needs driver ≥610; 591.74 only has the older API — 7.1 NVENC verified) + self-migrates an old build. scripts/benchmark.py times GPU-vs-CPU render + ffprobe-validates + times CPU transcribe. **CUDA whisper DROPPED (data): prebuilt cuBLAS 12.4 is ~40× slower than CPU on Blackwell — Windows transcribe stays CPU BLAS (~9× realtime); ACCEL-02/SAFE-02 deferred.**
- P15 macOS tuning: videotoolbox profile + Metal whisper; probe+fallback unit-tested with a stubbed Mac (picks h264_videotoolbox on darwin, falls back to x264 if absent) — untestable Mac path can't break.
- P16 branch split: windows-optimized + mac-optimized forked off the shared core (differ only in the README platform banner), each one-command quickstart, both pushed to github.com/Metdez/Content-Reels.

### Also fixed this session (regressions, verified live in-browser)

- Run crash (`transcript.json not found`): transcribe() re-derived a content-hash job id and wrote the transcript to the wrong dir while the pipeline ran under the per-upload nonce id — threaded the running Job into transcribe(). Verified: Run completes end-to-end, all 3 ratios render.
- Preview flashing: drawOut() sized the frame from its own mutated width (oscillated at the height cap) — size from the stable parent column. Verified: frame steady at 315px across 40 frames, canvas live.

### Verified live (v3, Windows 11, real binaries + browser + ffprobe)

- P9 transform model: compute_crop gains zoom + x/y pan; back-compat (8 prior render tests unchanged); 6 new unit tests. JS mirror is pixel-accurate (9:16 zoom2 → 202×360px).
- P10 pre-run preview: per-aspect zoom/pan with live WYSIWYG output frame; copy-to-all; slack-aware slider disable; transforms persist to run_params. Browser-verified pixel-parity with the renderer.
- P11 progress: weighted master bar + per-section bars; whisper-% transcribe; render per-aspect-per-clip counts; indeterminate select; screenshotted at 4 states (transcribe 35%, select indeterminate, render 2/6=67%, complete 100%).
- P12 clip editor: /job/{id}/clip/{idx}/edit — trim (snap-to-sentence), per-aspect reframe (+copy-to-all), caption text/timing edit + toggle, audio mute/volume; non-destructive edit.json; per-aspect re-render. EnlayeParis clip 1 trimmed 21.74s→13.78s across all 3 ratios (all aac, vol 0.8), mute drops audio stream, captions auto-re-derive, edit.json round-trips.

### v3 phase map (Phases 9–12)

- P9 Per-Aspect Transform Model + Crop Math — replace scalar `x_offset` with `{zoom, x, y}` per aspect in `render.compute_crop`; back-compat shim for old `x_offset` runs; unit tests (ZOOM-01/02/03)
- P10 Pre-Run Preview Upgrade — per-aspect zoom + x/y pan controls with live CSS preview mirroring the Python crop math; transforms become run defaults (ZOOM-04/05). Depends on P9.
- P11 Progress System — real transcribe % (whisper-cli) + render per-aspect-per-clip counts; weighted master + per-section bars; clips surface as they finish; Playwright-verified (PROG-01/02/03/04). Orthogonal to P9/P10.
- P12 Focused Clip Editor — `/job/{id}/clip/{idx}/edit`: trim (snap-to-sentence), per-aspect reframe (+copy-to-all), caption text/timing + toggle, audio keep/mute/volume; non-destructive `edit.json`; per-aspect re-render (EDIT-01..06). Depends on P9 + P10.

### Verified live (v2, Windows 11, real binaries + browser)

- P5 Windows port: transcribe(whisper-cli.exe) + select(claude.CMD) + render(ffmpeg) end-to-end; 28 tests pass
- P6 crop preview: upload stages → preview crop box+slider (matches compute_crop) → Run propagates x_offset
- P7 UI: studio redesign, stage stepper, clean live log (UTF-8)
- P8 audio+captions+reframe: 18/18 outputs have aac audio; uniform captions fit 9:16/1:1/16:9; reframe re-renders left/right with audio intact
- Full EnlayeParis.mp4: 6 clips selected with strong hooks, all 3 ratios each, thumbnails in review grid

### How to run

- `bash scripts/setup.sh` (one-time), then `content-machine serve` → http://127.0.0.1:8000
- CLI: `content-machine ingest <video>` → `select <job_id>` → `render <job_id>`

### Verified live

- P1 transcription correct on known-content video + VAD on silence + caching
- P2 `claude -p` selection (subscription) returns boundary-snapped clips + caching
- P3 3 aspect ratios + visible captions + thumbnails
- P4 web upload→progress→review→reframe→download

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: —
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- v3 framing model: replace the single scalar `run_params.x_offset` with a per-aspect transform `{zoom≥1, x∈[-1,1], y∈[-1,1]}`; each clip can override per aspect. Back-compat shim maps old `x_offset` → `{zoom:1, x:x_offset, y:0}` so v2 jobs/manifests keep rendering. (Phase 9)
- v3 live preview: the browser CSS-transform preview and the ffmpeg crop must share ONE crop-math definition (mirror/expose `render.compute_crop`) — divergence is the main risk, gated by a pixel-parity criterion. (Phases 10, 12)
- v3 editor scope: focused per-clip tool (trim, reframe, captions, audio) with non-destructive `edit.json` and per-aspect re-render — explicitly NOT a multi-track NLE (out of scope by decision). (Phase 12)
- v3 progress: drive the transcribe bar off real whisper-cli stderr %, render bar off deterministic `len(clips)×len(aspects)`; reuse polling-over-`job.json` (`update_stage`) before reaching for SSE. (Phase 11)
- Engine locked: whisper.cpp (transcribe) + ffmpeg (cut/crop/assemble) + Pillow PNG / hyperframes (captions). video-use is a pattern reference only, not a dependency.
- Clip selection = non-bare `claude -p` on the subscription only — no API-key fallback. Cached by transcript hash.

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 9: `x_offset` back-compat shim is load-bearing — live v2 jobs carry scalar `x_offset` in `render.json` run_params; `compute_crop`'s `(crop_w, crop_h, x, y)` return signature must stay stable so `crop_scale_filter`/`build_render_cmd` keep working.
- Phase 10/12: JS↔Python crop-math divergence is the recurring risk — share one definition, verify pixel parity on EnlayeParis.mp4.
- Phase 11: whisper-cli stderr progress format needs a quick parse spike before planning.
- Phase 12: per-aspect dirty-tracking ("only changed aspects re-encode") and the `edit.json` schema are the load-bearing unknowns — worth a short spike/`--research-phase`.

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Reframe | REFRAME-01 speaker-aware auto-reframe (CV/active-speaker) | Deferred (v2 backlog) | v1 |
| Captions | CAPS-01 word-level karaoke (forced alignment) | Deferred (v2 backlog) | v1 |
| Distribution | DIST-01/02/03 API-key fallback, LinkedIn publish, batch queue | Deferred | v1 |

## Session Continuity

Last session: 2026-06-30
Stopped at: v3 ROADMAP.md appended (Phases 9–12); REQUIREMENTS.md v3 traceability confirmed (15/15 → P9–P12); STATE.md total_phases set to 4
Resume file: None — next is `/gsd-plan-phase 9`
