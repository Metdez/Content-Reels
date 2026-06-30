"""Clip selection via Claude (subscription headless, `claude -p`).

The transcript is shown to Claude as numbered, timestamped segments. Claude
returns **segment index ranges** (not raw seconds), so every chosen clip snaps
to sentence boundaries by construction — no mid-sentence cuts. We then map
indices back to real timestamps, validate/clamp, dedup overlaps, and cache the
result by transcript hash so re-runs don't re-spend subscription limits.

Subscription note: we call DEFAULT (non-bare) `claude -p`, which uses the
`claude login` OAuth creds. `--bare` would force ANTHROPIC_API_KEY — exactly
what we're avoiding.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

from pydantic import BaseModel, Field

from . import config
from .jobs import Job
from .logging_setup import get_logger

log = get_logger(__name__)

MIN_CLIP_LEN = 12.0   # seconds — below this it's not a clip
MAX_CLIP_LEN = 90.0   # LinkedIn sweet spot upper bound
DEFAULT_MAX_CLIPS = 6
CHUNK_CHAR_BUDGET = 12_000  # rough transcript size that fits one comfortable pass


class Clip(BaseModel):
    start: float
    end: float
    start_seg: int
    end_seg: int
    title: str = ""
    rationale: str = ""
    score: float = Field(default=5.0, ge=0, le=10)

    @property
    def duration(self) -> float:
        return self.end - self.start


def _fmt_ts(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def transcript_hash(transcript: dict) -> str:
    return hashlib.sha256(
        json.dumps(transcript.get("segments", []), sort_keys=True).encode()
    ).hexdigest()[:16]


# --- prompt ------------------------------------------------------------------
def render_segments(segments: list[dict]) -> str:
    return "\n".join(
        f"[{i}] {_fmt_ts(s['start'])}-{_fmt_ts(s['end'])} {s['text'].strip()}"
        for i, s in enumerate(segments)
    )


def build_selection_prompt(segments: list[dict], max_clips: int = DEFAULT_MAX_CLIPS) -> str:
    return f"""You are an expert short-form video editor selecting clips for LinkedIn.

Below is a transcript as numbered segments: `[index] mm:ss-mm:ss text`.

Pick up to {max_clips} of the BEST standalone clips. Each clip:
- Has a strong hook in its first line and delivers a complete, self-contained idea.
- Is made of CONTIGUOUS segments (a start index through an end index, inclusive).
- Should run roughly {int(MIN_CLIP_LEN)}-{int(MAX_CLIP_LEN)} seconds.
- Does NOT start or end mid-thought (you choose whole segments, so respect sentence flow).

Score each 0-10 on likely LinkedIn performance (hook + value + quotability).

Respond with ONLY a JSON object, no prose:
{{"clips": [{{"start_seg": <int>, "end_seg": <int>, "title": "<=60 chars hook/title", "rationale": "one line why it works", "score": <number 0-10>}}]}}

Transcript:
{render_segments(segments)}
"""


# --- claude invocation -------------------------------------------------------
def build_claude_cmd() -> list[str]:
    # default (non-bare) -p => subscription OAuth; json wrapper gives us .result
    return [config.CLAUDE, "-p", "--output-format", "json"]


def extract_json_object(text: str) -> dict:
    """Pull the first balanced {...} JSON object out of possibly-chatty text."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in Claude output")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("Unbalanced JSON in Claude output")


def run_claude(prompt: str, timeout: int | None = None, attempts: int = 3) -> dict:
    """Run `claude -p` and return the parsed selection JSON object.

    Resilient (VAL-02 / bugs #2/#3/#4): the stdout parse is guarded (a raw
    `JSONDecodeError` never leaks — chatty/non-JSON stdout becomes a clear
    `RuntimeError`), `proc.stderr` is None-safe, and transient failures (timeout,
    non-zero exit, non-JSON output) are retried with backoff up to `attempts`
    times. `is_error` from the wrapper is a hard, non-retryable failure (e.g. a
    usage limit). When the caller doesn't pin `timeout`, it scales with prompt
    size so big transcripts get more headroom.
    """
    config.require_tool(config.CLAUDE, "Install Claude Code and run `claude login`.")
    if timeout is None:
        timeout = min(600, 120 + len(prompt) // 100)
    log.info("▶ claude -p selection (%d chars of transcript) — may take 20-60s", len(prompt))
    last_err: Exception | None = None
    for attempt in range(attempts):
        if attempt:
            time.sleep(1.5 ** attempt)
            log.info("↻ claude -p retry %d/%d", attempt + 1, attempts)
        t = time.time()
        try:
            proc = subprocess.run(build_claude_cmd(), input=prompt, capture_output=True,
                                  text=True, encoding="utf-8", errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired as e:
            last_err = e
            log.warning("claude -p timed out after %ss (attempt %d/%d)",
                        timeout, attempt + 1, attempts)
            continue
        if proc.returncode != 0:
            stderr = (proc.stderr or "")[:500]
            last_err = RuntimeError(f"claude -p failed ({proc.returncode}): {stderr}")
            log.warning("claude -p failed (%s) attempt %d/%d: %s",
                        proc.returncode, attempt + 1, attempts, stderr)
            continue
        try:
            wrapper = json.loads(proc.stdout)        # {type:result, result:"...", ...}
        except json.JSONDecodeError:
            head = (proc.stdout or "")[:200]
            last_err = RuntimeError(f"claude -p returned non-JSON output: {head}")
            log.warning("claude -p returned non-JSON output attempt %d/%d: %s",
                        attempt + 1, attempts, head)
            continue
        if wrapper.get("is_error"):                  # hard failure — don't retry
            log.error("✗ claude -p returned error: %s", wrapper.get("result"))
            raise RuntimeError(f"claude -p returned error: {wrapper.get('result')}")
        log.info("✓ claude -p selection (%.1fs)", time.time() - t)
        return extract_json_object(wrapper["result"])
    log.error("✗ claude -p failed after %d attempt(s): %s", attempts, last_err)
    raise RuntimeError(f"claude -p failed after {attempts} attempt(s): {last_err}")


# --- mapping + validation ----------------------------------------------------
def clips_from_indices(raw: dict, segments: list[dict]) -> list[Clip]:
    """Map Claude's segment-index ranges to real timestamped, validated clips."""
    n = len(segments)
    out: list[Clip] = []
    for c in raw.get("clips", []):
        try:
            a = max(0, min(int(c["start_seg"]), n - 1))
            b = max(0, min(int(c["end_seg"]), n - 1))
        except (KeyError, TypeError, ValueError):
            continue
        if b < a:
            a, b = b, a
        clip = Clip(
            start=segments[a]["start"],
            end=segments[b]["end"],
            start_seg=a, end_seg=b,
            title=str(c.get("title", "")).strip()[:80],
            rationale=str(c.get("rationale", "")).strip(),
            score=float(c.get("score", 5.0)),
        )
        out.append(clip)
    return out


def dedup_and_filter(clips: list[Clip], max_clips: int = DEFAULT_MAX_CLIPS) -> list[Clip]:
    """Drop too-short clips and overlapping duplicates; keep highest score first."""
    ranked = sorted(clips, key=lambda c: c.score, reverse=True)
    chosen: list[Clip] = []
    for c in ranked:
        if c.duration < MIN_CLIP_LEN:
            continue
        if any(c.start_seg <= o.end_seg and o.start_seg <= c.end_seg for o in chosen):
            continue  # overlaps an already-chosen (higher-scored) clip
        chosen.append(c)
        if len(chosen) >= max_clips:
            break
    return sorted(chosen, key=lambda c: c.start)  # timeline order for output


# --- long transcripts --------------------------------------------------------
def chunk_segments(segments: list[dict], char_budget: int = CHUNK_CHAR_BUDGET) -> list[list[int]]:
    """Split into index-chunks under a char budget; returns lists of global indices."""
    chunks, cur, size = [], [], 0
    for i, s in enumerate(segments):
        seg_len = len(s.get("text", ""))
        if cur and size + seg_len > char_budget:
            chunks.append(cur)
            cur, size = [], 0
        cur.append(i)
        size += seg_len
    if cur:
        chunks.append(cur)
    return chunks


# --- orchestration -----------------------------------------------------------
def select_clips(job_id_or_job, max_clips: int = DEFAULT_MAX_CLIPS,
                 force: bool = False) -> Path:
    job = job_id_or_job if isinstance(job_id_or_job, Job) else Job.load(job_id_or_job)
    transcript = json.loads(job.transcript_path.read_text())
    segments = transcript.get("segments", [])
    if not segments:
        raise ValueError("Transcript has no segments — run ingest first.")

    thash = transcript_hash(transcript)
    if job.clips_json_path.exists() and not force:
        existing = json.loads(job.clips_json_path.read_text())
        if existing.get("transcript_hash") == thash:
            log.info("select: cache hit — reusing existing clips.json")
            job.update_stage("select", "done", cached=True)
            return job.clips_json_path

    job.update_stage("select", "running")
    chunks = chunk_segments(segments)
    log.info("select: %d segments in %d chunk(s)", len(segments), len(chunks))
    all_clips: list[Clip] = []
    failures = 0
    for idxs in chunks:
        sub = [segments[i] for i in idxs]
        try:
            raw = run_claude(build_selection_prompt(sub, max_clips))
        except Exception as e:  # VAL-02: skip a bad chunk, don't abort the stage
            failures += 1
            log.warning("select: chunk of %d segment(s) failed — skipping: %s", len(idxs), e)
            continue
        # remap chunk-local indices in `raw` to global before mapping
        for c in raw.get("clips", []):
            c["start_seg"] = idxs[max(0, min(int(c.get("start_seg", 0)), len(idxs) - 1))]
            c["end_seg"] = idxs[max(0, min(int(c.get("end_seg", 0)), len(idxs) - 1))]
        all_clips.extend(clips_from_indices({"clips": raw.get("clips", [])}, segments))

    if failures and not all_clips:  # every chunk failed and nothing was produced
        raise RuntimeError(
            f"select: all {len(chunks)} transcript chunk(s) failed claude -p selection")

    chosen = dedup_and_filter(all_clips, max_clips)
    log.info("select: %d candidate(s) -> %d clip(s) after dedup/filter",
             len(all_clips), len(chosen))
    payload = {
        "transcript_hash": thash,
        "clips": [c.model_dump() for c in chosen],
    }
    job.clips_json_path.write_text(json.dumps(payload, indent=2))
    job.update_stage("select", "done", clips=len(chosen))
    return job.clips_json_path
