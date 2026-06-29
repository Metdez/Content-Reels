# Phase 4 Summary: Localhost UI + Job Runner

**Status:** ✅ Complete — full upload→pipeline→review→reframe→download flow verified live.

## What shipped
- `content_machine/app.py` — FastAPI app:
  - background pipeline runner (daemon thread: transcribe → select → render); stages write to `job.json`, browser polls `/api/job/{id}`.
  - filesystem-as-library (`list_jobs()` globs `data/*/job.json`) — no DB.
  - routes: `/` (library+upload), `/upload`, `/job/{id}`, `/api/job/{id}`, `/api/job/{id}/clip/{idx}/reframe`, `/download/{id}/{idx}/{aspect}`, `/media/*` static.
  - Jinja2 driven directly with `cache_size=0` (Starlette's Jinja2Templates hits a jinja2 LRUCache bug on Python 3.14).
- `content_machine/templates/{index,job}.html` — dark UI: upload form, library table, progress stages, clip cards (video player, aspect tabs, title/score/rationale, crop slider + re-frame, downloads).
- `render.rerender_one` — single-clip re-render for the crop-offset tweak.
- `cli.py` — `content-machine serve`.
- `tests/test_app.py` — 4 tests (status rollup, fs library, media URL, payload merge).

## Verification (success criteria) — all live
- UI-01 ✅ upload → 303 → job page
- UI-02 ✅ background job, progress polled `running`→`done`
- UI-03 ✅ review clips (player, title, score, rationale, thumbnail)
- UI-04 ✅ reframe re-renders (mtime changed; crop x 438→656 at offset 0.5)
- UI-05 ✅ download → HTTP 200 video/mp4
- UI-06 ✅ library browsable; `/media/*` serves clips+thumbs

## Decisions / notes
- `# ponytail:` library = filesystem (`data/*/job.json`), not SQLite — a directory glob is the index for one local user; architecture research endorsed this. (Deviation from the SQLite mention in REQUIREMENTS UI-06, by design.)
- Job runner is in-process threads (single user, one job in flight is fine); `job.json` is the source of truth so progress survives restarts.
- Binds `127.0.0.1` only (local-first).
