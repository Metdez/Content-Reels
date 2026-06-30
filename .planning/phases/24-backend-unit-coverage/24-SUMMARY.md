---
phase: 24
name: Backend Unit Coverage
status: complete
requirements: [QA-06, QA-07, QA-08, QA-09, QA-10, QA-11]
completed: 2026-06-30
---

# Phase 24 — Backend Unit Coverage — SUMMARY

**Outcome:** +92 characterization tests across the previously-untested/low-coverage backend modules, written in parallel by 6 subagents (one new file each). **Overall coverage 64.2% → 89.2%; 156 tests pass; ruff clean.** No product code changed (pure tests); bugs found are logged below for their fix phases.

## What shipped (6 new test files, +92 tests)
| File | Tests | Module | Coverage |
|------|-------|--------|----------|
| `tests/test_config.py` | 14 | config.py | 81.8% → **100%** (QA-06) |
| `tests/test_cli.py` | 9 | cli.py | 0% → **97.9%** (QA-07) |
| `tests/test_logging_setup.py` | 16 | logging_setup.py | 45.7% → **100%** (QA-08) |
| `tests/test_render_orchestration.py` | 21 | render.py | 46.2% → **98.6%** (QA-09) |
| `tests/test_captions_extra.py` | 18 | captions.py | 66.0% → **98.9%** (QA-10) |
| `tests/test_select_transcribe.py` | 14 | select/transcribe | 62.4%/78.7% → **95.7%/92.9%** (QA-11) |

Coverage approach: external binaries (ffmpeg/ffprobe/whisper/claude) stubbed (`stream_run`/`run`/`subprocess.run` monkeypatched); `logging_setup` exercised against a real trivial python subprocess (the point — it's the primitive under every tool call). Each agent ran its file with `--no-cov -p no:cacheprovider` to avoid `.coverage` races; the consolidated run (`pytest -q`) is green at 89.2%.

## Remaining coverage gaps (intentional, addressed elsewhere)
- **app.py 74.5%** — endpoint request-boundary paths; covered next in **Phase 25** (HTTP integration tests).
- **hwaccel.py 60.3%** — the real `_probe` is a hardware/subprocess call (always mocked); the selection logic is covered.

## Bugs found (characterized as tests against CURRENT behavior — NOT fixed here)
| # | Bug | Location | Fix phase |
|---|-----|----------|-----------|
| 1 | `rerender_one` does a non-atomic read-modify-write of `render.json` (read stale → build `others` → `write_text`); a concurrent clip update between read and write is silently lost. `render_job` rewrites the whole manifest the same way. | `render.py:350-362, 400` | **26 (REL-01/REL-02)** |
| 2 | `run_claude` does `json.loads(proc.stdout)` with no guard → leaks a raw `JSONDecodeError` when claude exits 0 but emits chatty/non-JSON stdout. | `select.py:130` | **28 (VAL-02)** |
| 3 | No retry/backoff: `select_clips` calls `run_claude` per chunk with no `try/except`, so one bad/timed-out/chatty chunk aborts the whole multi-chunk selection (no partial results). | `select.py:217` | **28 (VAL-02)** |
| 4 | Minor latent: `proc.stderr[:500]` (vs the safe `(proc.stderr or "")` one line up) would `TypeError` if stderr were ever None (not reachable today). | `select.py:129` | 28 (opportunistic) |
| 5 | `stream_run` silently swallows `on_line` callback exceptions (`except Exception: pass`) and raises `CalledProcessError` with **no** captured output attached — a buggy progress parser fails invisibly and failures lose stderr. | `logging_setup.py:123-124, 131` | note for **30** (error surfacing) |

Non-bug noted: job logs always write to `<repo>/logs/jobs/` (not DATA_DIR) — intentional per the module docstring.

## Verification
- `pytest -q` → **156 passed**, coverage **89.2%**.
- `ruff check content_machine tests` → clean.

## Improvement criteria applied
Advances **Test coverage** (the headline) and sets up **Reliability/Correctness** fixes by pinning current behavior with characterization tests so the Phase 26/28 fixes can flip them to the correct assertions. No behavior changed.
