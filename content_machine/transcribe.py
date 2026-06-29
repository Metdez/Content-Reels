"""Audio extraction + whisper.cpp transcription with a silence-based VAD filter.

Pipeline: video --ffmpeg--> 16kHz mono wav --whisper.cpp--> full JSON
--parse--> segments(+words) --VAD filter--> transcript.json

The VAD filter exists to kill whisper's classic silence hallucinations
("Thanks for watching", "you", music notes) without a second ML model: we ask
ffmpeg `silencedetect` where the silent ranges are, then drop any transcript
segment that sits (almost) entirely inside detected silence.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from . import config
from .jobs import Job
from .logging_setup import get_logger, run, stream_run

log = get_logger(__name__)

# Common whisper silence hallucinations (normalized, lowercase, no punctuation).
HALLUCINATION_BLOCKLIST = {
    "thanks for watching",
    "thank you",
    "thank you for watching",
    "you",
    "bye",
    "subscribe",
    "please subscribe",
    "see you next time",
    "music",
}


# --- ffmpeg: audio extraction -----------------------------------------------
def build_ffmpeg_audio_cmd(video: Path, out_wav: Path) -> list[str]:
    return [
        config.FFMPEG, "-y", "-i", str(video),
        "-vn", "-ac", "1", "-ar", str(config.AUDIO_SAMPLE_RATE),
        "-c:a", "pcm_s16le", str(out_wav),
    ]


def extract_audio(video: Path, out_wav: Path) -> Path:
    config.require_tool(config.FFMPEG, "Install ffmpeg: brew install ffmpeg")
    run(build_ffmpeg_audio_cmd(video, out_wav), log, "extract audio (16kHz mono)")
    return out_wav


# --- whisper.cpp -------------------------------------------------------------
def build_whisper_cmd(audio: Path, model: Path, out_prefix: Path,
                      language: str | None = None) -> list[str]:
    cmd = [
        str(config.WHISPER_CLI),
        "-m", str(model),
        "-f", str(audio),
        "--output-json-full",
        "-of", str(out_prefix),
        "-pp",
    ]
    if language:
        cmd += ["-l", language]
    return cmd


def run_whisper(audio: Path, model: Path, out_prefix: Path,
                language: str | None = None) -> Path:
    config.require_tool(
        config.WHISPER_CLI,
        "Build whisper.cpp: bash scripts/setup.sh (clones + builds vendor/whisper.cpp)",
    )
    if not model.exists():
        name = model.stem.removeprefix("ggml-")  # ggml-small.en.bin -> small.en
        raise FileNotFoundError(
            f"Whisper model missing: {model}\n"
            f"  → bash vendor/whisper.cpp/models/download-ggml-model.sh {name}"
        )
    # stream_run tees whisper's -pp progress to the log so a long transcription
    # shows live percentage instead of looking frozen.
    stream_run(build_whisper_cmd(audio, model, out_prefix, language), log,
               f"whisper transcription ({model.name})")
    return out_prefix.with_suffix(".json")


# --- parsing -----------------------------------------------------------------
def _ms(entry: dict, key: str) -> float:
    return entry.get("offsets", {}).get(key, 0) / 1000.0


def parse_whisper_json(raw: dict) -> dict:
    """whisper.cpp full JSON -> {language, segments:[{start,end,text,words:[]}]}."""
    language = raw.get("result", {}).get("language", "")
    segments = []
    for seg in raw.get("transcription", []):
        text = seg.get("text", "").strip()
        if not text:
            continue
        start, end = _ms(seg, "from"), _ms(seg, "to")
        words = []
        for tok in seg.get("tokens", []):
            ttext = tok.get("text", "")
            # skip special tokens like [_BEG_], [_TT_123], punctuation-only pieces
            if ttext.startswith("[") or not ttext.strip():
                continue
            words.append({
                "word": ttext.strip(),
                "start": _ms(tok, "from"),
                "end": _ms(tok, "to"),
            })
        segments.append({"start": start, "end": end, "text": text, "words": words})
    duration = segments[-1]["end"] if segments else 0.0
    return {"language": language, "duration": duration, "segments": segments}


# --- VAD / hallucination filter ---------------------------------------------
_SILENCE_END_RE = re.compile(r"silence_end:\s*([0-9.]+)")
_SILENCE_DUR_RE = re.compile(r"silence_duration:\s*([0-9.]+)")


def parse_silencedetect(stderr: str) -> list[tuple[float, float]]:
    """Parse ffmpeg silencedetect stderr into [(start, end), ...] silent ranges."""
    ranges: list[tuple[float, float]] = []
    for line in stderr.splitlines():
        m_end = _SILENCE_END_RE.search(line)
        if m_end:
            end = float(m_end.group(1))
            m_dur = _SILENCE_DUR_RE.search(line)
            dur = float(m_dur.group(1)) if m_dur else 0.0
            ranges.append((max(0.0, end - dur), end))
    return ranges


def detect_silence(audio: Path, noise_db: int = -35, min_silence: float = 0.8) -> list[tuple[float, float]]:
    cmd = [config.FFMPEG, "-i", str(audio), "-af",
           f"silencedetect=noise={noise_db}dB:d={min_silence}", "-f", "null", "-"]
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return parse_silencedetect(proc.stderr)


def _overlap(a: tuple[float, float], b: tuple[float, float]) -> float:
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def vad_filter(segments: list[dict], silence_ranges: list[tuple[float, float]],
               coverage: float = 0.9) -> list[dict]:
    """Drop segments that sit (>= `coverage`) inside a detected silent range and
    whose text is a known hallucination — silence + boilerplate = phantom text."""
    kept = []
    for seg in segments:
        span = max(1e-6, seg["end"] - seg["start"])
        silent = sum(_overlap((seg["start"], seg["end"]), r) for r in silence_ranges)
        norm = re.sub(r"[^a-z ]", "", seg["text"].lower()).strip()
        if silent / span >= coverage and norm in HALLUCINATION_BLOCKLIST:
            continue
        kept.append(seg)
    return kept


# --- orchestration -----------------------------------------------------------
def transcribe(video_path: str | Path, model: str | None = None,
               vad: bool = True, force: bool = False, language: str | None = None) -> Job:
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    job = Job.for_video(video_path)
    job.ensure_dirs()
    log.info("transcribe: job %s from %s (%.1f MB)", job.job_id, video_path.name,
             video_path.stat().st_size / 1e6)

    # cache: same content hash -> reuse transcript
    if job.transcript_path.exists() and not force:
        log.info("transcribe: cache hit — reusing existing transcript")
        job.update_stage("transcribe", "done", cached=True)
        return job

    # stage: ingest (copy source)
    job.update_stage("ingest", "running")
    src = job.source_path(video_path.suffix)
    if not src.exists():
        shutil.copy2(video_path, src)
    job.update_stage("ingest", "done", source=str(src))

    # stage: transcribe
    job.update_stage("transcribe", "running")
    extract_audio(src, job.audio_path)
    model_p = config.model_path(model)
    raw_json = run_whisper(job.audio_path, model_p, job.data_dir / "whisper", language)
    transcript = parse_whisper_json(json.loads(Path(raw_json).read_text()))

    if vad:
        before = len(transcript["segments"])
        silence = detect_silence(job.audio_path)
        transcript["segments"] = vad_filter(transcript["segments"], silence)
        transcript["vad_dropped"] = before - len(transcript["segments"])
        log.info("VAD: dropped %d silent/hallucinated segment(s)", transcript["vad_dropped"])

    job.transcript_path.write_text(json.dumps(transcript, indent=2))
    log.info("transcribe: done — %d segments, %.1fs",
             len(transcript["segments"]), transcript["duration"])

    manifest = job.load_manifest()
    manifest.setdefault("tools", {})["whisper_model"] = model or config.DEFAULT_MODEL
    job.save_manifest(manifest)
    job.update_stage("transcribe", "done",
                     segments=len(transcript["segments"]),
                     duration=transcript["duration"])
    return job
