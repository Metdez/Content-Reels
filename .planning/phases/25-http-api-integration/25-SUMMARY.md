---
phase: 25
name: HTTP API Integration Tests
status: complete
requirements: [API-01, API-02, API-03, API-04, API-05]
completed: 2026-06-30
---

# Phase 25 — HTTP API Integration Tests — SUMMARY

**Outcome:** `tests/test_api.py` — 22 HTTP-boundary tests through the `client`/`seeded_job` fixtures, covering every `app.py` route. **app.py 74.5% → 85.4%; overall 89.2% → 92.2%; 178 tests pass; ruff clean.** First real exercise of request parsing, status codes, and error paths. Pure tests; bugs logged below.

## Coverage (API-01..05)
- **API-01** `/upload`: valid → 303 + manifest; missing file / bad ext / dotfile / traversal handled (probe stubbed).
- **API-02** `/run`: ok (thread stubbed) / 409 re-run / 404 unknown / 400 missing source.
- **API-03** `/api/job/{id}`, `/log?lines=`, `/clip/{idx}` GET + 404s.
- **API-04** `/clip/{idx}/edit` <0.5s → 400, valid → `{queued}` (enqueue stubbed); `/rerender-status` idle shape.
- **API-05** `/download` 200/404; `/media` scope; legacy `/reframe` (render stubbed).

## Bugs found (characterized, NOT fixed)
| # | Bug | Location | Fix phase |
|---|-----|----------|-----------|
| A | **`/upload` reverts `ingest` to `pending`**: `update_stage("ingest","done")` persists done, then a trailing `save_manifest(manifest)` writes back the in-memory manifest loaded *before* the update — clobbering ingest to `pending` on disk. | `app.py:349-355` | **27** |
| B | Dead 400 guard: `if not video.filename` is unreachable — Starlette returns 422 for an empty-filename part before the guard. | `app.py:319-320` | 28 (cleanup) |
| C | **VAL-05** `/media` mount over `DATA_DIR` serves `job.json`/`transcript.json`/`audio.wav` verbatim (confirmed 200 with full manifest). | `app.py:64` | **28** |
| D | Traversal `../escape.mp4` is neutralized to basename (303 success), not rejected with 400 — safe in effect, differs from a reject expectation. | `app.py:42-49` | by design (note) |

## Verification
- `pytest -q` → **178 passed**, coverage 92.2%; `ruff check` clean.

## Improvement criteria applied
Advances **Test coverage** (request-boundary) and **Reliability/Correctness** prep — bug A (ingest revert) and C (VAL-05) now have failing-on-fix characterization tests ready for Phases 27/28.
