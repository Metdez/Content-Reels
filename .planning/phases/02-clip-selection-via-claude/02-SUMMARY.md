# Phase 2 Summary: Clip Selection via Claude

**Status:** ✅ Complete — verified live against `claude -p` (subscription, non-bare).

## What shipped
- `content_machine/select.py`:
  - `build_selection_prompt` — shows transcript as numbered `[i] mm:ss-mm:ss text`; asks Claude for **segment index ranges** + title/rationale/score.
  - `run_claude` — `claude -p --output-format json` over stdin (subscription OAuth, no API key); `extract_json_object` tolerates chatty output.
  - `clips_from_indices` — maps index ranges → real timestamps (auto-snaps to sentence boundaries), clamps OOB, fixes reversed ranges.
  - `dedup_and_filter` — drops <12s and overlapping clips, keeps highest score, returns timeline order.
  - `chunk_segments` — splits long transcripts under a char budget (two-pass for big inputs).
  - Caches `clips.json` by `transcript_hash` to conserve subscription limits.
  - `Clip` pydantic model.
- `cli.py` — `content-machine select <job_id>`.
- `tests/test_select.py` — 6 passing tests (prompt, JSON extraction, mapping/clamp, dedup, chunking, hash).

## Verification (success criteria)
- SELECT-01 ✅ structured clip list from `claude -p`
- SELECT-02 ✅ rubric (hook/value/quotability) → picked "Your best sales rep is a happy customer" (8.0) w/ rationale
- SELECT-03 ✅ boundary-snapped by construction (start==seg.start, end==seg.end)
- SELECT-04 ✅ cached by transcript hash (re-run 0.1s, `cached=True`)
- SELECT-05 ✅ schema validation + chatty-JSON extraction + chunking

## Decisions / notes
- Index-range selection (not raw seconds) is the key trick: snapping is free and Claude can't emit mid-sentence cuts. `# ponytail:` no separate snap pass needed.
- Subscription risk accepted (per PROJECT.md); mitigated by transcript-hash cache. One `claude -p` call per chunk per video.
- `clips.json` schema: `{transcript_hash, clips:[{start,end,start_seg,end_seg,title,rationale,score}]}` — consumed by Phase 3 render.
