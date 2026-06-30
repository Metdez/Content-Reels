---
phase: 24
name: Backend Unit Coverage
wave: 1
requirements: [QA-06, QA-07, QA-08, QA-09, QA-10, QA-11]
autonomous: true
---

# Phase 24 — Backend Unit Coverage

**Goal:** Close the unit-test gaps on the modules with zero/low coverage (cli 0%, logging_setup 46%, render 46%, captions 66%, select 62%), external binaries stubbed, so tests stay fast + deterministic. Characterization tests against CURRENT behavior; any bug found is reported for the relevant fix phase (26–28/30–31), NOT fixed here.

## Tasks (one new test file each — parallelizable)
1. **QA-06** `tests/test_config.py` — `_resolve_binary` (env/PATH/vendor/bare), `_resolve_whisper_cli`, `model_path`, `require_tool` (raises w/ hint).
2. **QA-07** `tests/test_cli.py` — Typer `CliRunner` smoke of `ingest`/`select`/`render`/`serve` with heavy stages monkeypatched.
3. **QA-08** `tests/test_logging_setup.py` — `stream_run`/`run` against a trivial real subprocess (python -c), `tail`, `job_log`/`job_log_path`, `get_logger`.
4. **QA-09** `tests/test_render_orchestration.py` — `render_clip`/`render_job`/`rerender_one` with `stream_run`/encode stubbed; assert render.json shape, progress callbacks, thumbnail, per-aspect outputs, `probe_dims`/`audio_chain`/`build_overlay_cmd`/`build_thumbnail_cmd`.
5. **QA-10** `tests/test_captions_extra.py` — `fit_caption` auto-size, `find_font`, `render_caption_pngs` batch, and the hyperframes-gated path (`hyperframes_available`/`build_caption_composition`/`render_hyperframes_overlay`) with subprocess stubbed.
6. **QA-11** `tests/test_select_transcribe.py` — `select.run_claude` failure handling (timeout, non-zero, non-JSON), `select_clips` multi-chunk merge; transcribe `extract_audio`/`detect_silence` cmd builders + `run_whisper` progress-callback parsing (stub subprocess).

## Verify (exit criteria)
- Each new file passes; full `pytest -q` green; overall coverage rises measurably over 64.2%.
- cli.py, logging_setup.py, render.py, captions.py coverage materially up.
- ruff clean on the new test files.
- Any discovered bug logged in this SUMMARY under "Bugs found (deferred to fix phase)".

## Notes
- Agents run their own file with `.venv/Scripts/python.exe -m pytest tests/test_X.py --no-cov -p no:cacheprovider -q` (avoids concurrent `.coverage` races).
- Pure tests only — do NOT modify `content_machine/` product code.
