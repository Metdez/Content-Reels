# Phase 1 Summary: Pipeline Spine — Ingest + Transcribe

**Status:** ✅ Complete — verified end-to-end on real binaries (ffmpeg 8.1.2, whisper.cpp Metal, base.en)

## What shipped
- Python package `content_machine` (Python 3.11+; built/tested on 3.14).
- `config.py` — resolves local tool paths (ffmpeg, vendored whisper-cli, claude), data dir, defaults; `require_tool` gives actionable errors.
- `jobs.py` — content-hash `job_id`, `data/<job_id>/` layout, `job.json` manifest with per-stage status (ingest/transcribe/select/render).
- `transcribe.py` — ffmpeg audio extract (16k mono) → whisper.cpp `--output-json-full` → parse segments + word timing → ffmpeg `silencedetect` VAD filter (drops hallucinations in silence) → `transcript.json`; cache by content hash.
- `cli.py` — `content-machine ingest <video>`.
- `scripts/setup.sh` — idempotent: brew deps, clone+build whisper.cpp (Metal), download model, venv, install, smoke test.
- `tests/test_pipeline.py` — 8 passing pure-logic tests.

## Verification (success criteria)
1. ✅ `ingest` on real mp4 → `data/<id>/{source.mp4, audio.wav, transcript.json, job.json}`
2. ✅ Transcript exact on known-content (`say`-generated) video, with word timing
3. ✅ Silent clip → 0 segments, VAD dropped 1 phantom
4. ✅ Re-run reuses cache (0.1s vs 13s; `transcribe.cached=True`)

## Decisions / notes
- VAD = ffmpeg `silencedetect` + hallucination blocklist (no second ML model). `# ponytail:` dependency-free; upgrade to Silero VAD model if it misses.
- Word timing is token-derived (approximate, ±~300ms) — fine; precise snapping handled in Phase 2/3.
- Default model `base.en` (148MB) for speed; configurable via `--model` / `CM_WHISPER_MODEL`.

## For later phases
- `Job` gives `clips_json_path`, `clips_dir` already — Phase 2 writes `clips.json`, Phase 3 fills `clips/`.
- `transcript.json` schema: `{language, duration, segments:[{start,end,text,words:[{word,start,end}]}]}`.
