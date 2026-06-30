# v6 Discovery Inventory — Content Machine

**Date:** 2026-06-30
**Method:** Full read of `content_machine/` (10 modules), 3 templates, 5 test files, `tools/hyperframes`, `vendor/whisper.cpp`, docs, and `.planning/`, via four parallel mapping agents. This is the Phase 0 deliverable that the v6 roadmap is derived from.

---

## (a) Features & user-facing flows

1. **Upload → job creation** — drag/drop or pick a video (`index.html`), `POST /upload` stages it, probes dims, marks `awaiting_run` (no processing yet).
2. **Pre-run framing** — per-aspect zoom + X/Y pan with a live WYSIWYG output canvas for 9:16/1:1/16:9, copy-to-all, reset, slack-aware slider disable (`job.html` preview state).
3. **Run pipeline** — `POST /run` spawns a background thread: transcribe (whisper.cpp) → select (`claude -p`) → render (ffmpeg, 3 aspects/clip + thumbnail).
4. **Live progress** — weighted master bar + 4-step stepper (ingest/transcribe/select/render), real whisper-% + per-aspect-per-clip render counts, live log tail; clips stream into the grid as they finish.
5. **Clip review grid** — per-clip card with aspect tabs, title/score/rationale, download per aspect.
6. **Quick-crop modal** — per-aspect zoom+X+Y, live preview, scroll-zoom + drag-pan, non-blocking re-render with progress bar + per-aspect status + live log (`job.html`).
7. **Full clip editor** (`/job/{id}/clip/{idx}/edit`) — reframe (zoom/X/Y per aspect + magnifier), trim with sentence-boundary snapping, caption text/timing + toggle, audio mute/volume, non-blocking re-render with flow-state pill.
8. **Download** — `GET /download/{job}/{idx}/{aspect}`.
9. **GPU-accelerated render** — NVENC/VideoToolbox encode with mandatory CPU (x264) fallback; CPU decode + filters by design.
10. **CLI** — `content-machine ingest|select|render|serve`, same pipeline headless.

## (b) Pages / routes / components

- **Pages:** `/` (index/library), `/job/{id}` (preview OR progress+clips), `/job/{id}/clip/{idx}/edit` (editor).
- **JSON/file APIs:** `/upload`, `/api/job/{id}/run`, `/api/job/{id}`, `/api/job/{id}/log`, `/api/job/{id}/clip/{idx}` (GET), `/api/job/{id}/clip/{idx}/edit` (POST), `/api/job/{id}/clip/{idx}/rerender-status`, `/api/job/{id}/clip/{idx}/reframe` (**legacy/unused**), `/download/{id}/{idx}/{aspect}`, `/media/*` (StaticFiles over **all** of DATA_DIR).
- **Data structures:** `job.json`, `transcript.json` (segments **+ unused `words[]`**), `clips.json`, `clips/render.json`, `clips/clipNN/edit.json`; per-aspect transform `{zoom≥1, x∈[-1,1], y∈[-1,1]}`.
- **Components:** duplicated `computeCrop`/`drawBox`/`drawOut` crop math (2 JS copies + 1 Python), aspect tabs, sliders, crop-box overlay, output canvas RAF loop, progress stepper, re-render status rows, flow-state pill.

## (c) Known gaps & fragile areas

**Backend (cite app.py/render.py/jobs.py/select.py/transcribe.py):**
- **C1 (critical):** non-atomic `job.json`/`render.json` writes (`jobs.py:103`, `render.py:362/400`) — high-frequency progress writes + concurrent polls → truncated-JSON read → uncaught 500 in `_job_payload`/`api_job`. Cross-clip `render.json` lost-update when two clips re-render at once.
- **H1 (high):** `/upload` is `async def` (`app.py:312`) but does sync whole-file SHA-256 + copy (`app.py:327/334`, `jobs.py:32`) → freezes event loop + all polls during large uploads.
- **H2 (high):** in-flight error state is memory-only (`RUNNING`, `app.py:68`) — lost on restart; daemon pipeline threads (`app.py:400`) killed abruptly → partial `render.json` + orphaned ffmpeg.
- **M (medium):** no trim-bound validation beyond ≥0.5s (`app.py:513`) — no `start≥0`/`end≤duration`; no `zoom` upper bound (`render.py:69`). `/media` serves entire data dir (`app.py:65`). Per-chunk `claude -p` no retry, fixed 180s timeout (`select.py:125/216`).
- **L (low):** same-name concurrent upload collision (`app.py:326`); raw `ValueError` on empty transcript (`select.py:202`); Windows-wrong `brew install` hints (`transcribe.py:50`, `render.py:238`); no concurrency cap → NVENC session exhaustion.

**Frontend (cite job.html/editor.html/index.html):**
- **Crop drift:** `computeCrop` duplicated verbatim (`job.html:196`, `editor.html:137`) + Python = 3 sync points; `drawBox`/`drawOut` also diverge; both use **video intrinsic dims, not `source_dims`** (`editor.html:162`, `job.html:237`) — preview can mismatch render.
- **Error swallowing → stuck UI:** `editor.pollRender` `.catch(()=>{})` (`:237`) leaves pill "⟳ Rendering…" forever; `job.poll` swallows 404 (`:581`) and polls forever; log polls swallow all.
- **"Re-derive from transcript" is a no-op** (`editor.html:437`) — fetches but never parses; can't reflect a changed trim.
- **Boot crash risk:** `D.captions` assumed non-null (`editor.html:491`).
- **Dirty cleared before POST confirms** (`editor.html:462`); modal failure leaves half-open progress UI (`job.html:542`).
- **Stale cache** on reconcile rebuild — `clipEl` emits `<video>` with no `?t=` (`job.html:405`).
- **No source scrub controls / force-muted** editor video (`editor.html:269`) → audio edits unauditionable.
- **No caption time validation** (`editor.html:431`).
- **Accessibility:** interactive `<span>`s not buttons, modal has no `role=dialog`/focus-trap/ESC, sliders unlabeled, color-only state, log not `aria-live`, icon-only buttons unlabeled.
- **Mobile/responsive:** wheel-zoom scroll trap, 12px trim handles (<44px), inconsistent preview CAP (560/420/540); index drop has no type/size check; run errors use blocking `alert()`.

**Tests/quality:**
- 58 tests pass (2.4s) but all unit-level command-builders. **Zero HTTP-layer tests** (no `TestClient`); **zero tests** for `config.py`, `cli.py`, `logging_setup.py` (incl `stream_run`, the subprocess primitive under every external call). Untested: render orchestration (`render_clip`/`render_job`/real `rerender_one`), captions hyperframes + `fit_caption`, `select.run_claude` failure, transcribe binary layers. **No lint/format/typecheck, no CI, no E2E.**

## (d) Candidate features from referenced repos

- **whisper.cpp** — `transcript.json` **already persists per-word `{word,start,end}`** but nothing reads it. Unlocks: word-boundary cut-snapping (**S**), word-level karaoke captions (**M**). Also: selectable larger model (`small/medium.en`, **S**); native VAD binary (**S–M**, low priority).
- **hyperframes** — already **wired as a self-healing fallback** (`captions.py:145-213`, `render.py:273-293`); default is Pillow PNG. Finishing it = animated/karaoke captions: real scaffolded composition/template + Chrome provisioning in setup (**M**). It is the natural home for CAPS-01.
- **video-use** — reference-only (cloud STT breaks local-first). Borrowable idea: a unified transcript-anchored **EDL** that selection/editor/render all read (**M**, optional).
- **DeepAgentLLMtxt.md** — **0 bytes / empty.** CLAUDE.md calls it "LangSmith/Fleet docs" but there is nothing to extract. **Flagged for the user** — needs content sourced or the reference dropped.
- **Out of scope (confirmed):** speaker-aware auto-reframe (REFRAME-01, needs CV — large), LinkedIn auto-publish, multi-user, full NLE, GPU decode.

---

## "Better" criteria (explicit standard for the Improve work)

Improvements in v6 are judged against, in priority order:
1. **Correctness** — output matches intent (crop parity, valid trims/captions).
2. **Reliability** — no crashes, no races, no truncated reads, graceful failure + recovery.
3. **Error handling / UX clarity** — every failure surfaces a readable message; no silent hangs; always-visible state.
4. **Accessibility** — WCAG 2.1 AA where feasible (keyboard, roles, labels, contrast, aria-live).
5. **Test coverage** — every feature/flow has a passing automated check.
6. **Performance** — no event-loop blocking; no needless re-encode/re-buffer.
7. **Code quality** — DRY (one crop module), clear seams, no dead/legacy paths.

A change ships only when it improves at least one criterion without regressing another, and is covered by a test.
