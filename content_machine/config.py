"""Resolved paths and defaults. Everything is local; env vars override.

The whole app shells out to three local tools:
  - ffmpeg / ffprobe (Homebrew)         — audio extract + render
  - whisper.cpp whisper-cli (vendored)  — transcription
  - claude -p (Claude Code subscription)— clip selection

Paths resolve relative to the project root (this file's grandparent) so the
app works regardless of the current working directory.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --- Local storage -----------------------------------------------------------
DATA_DIR = Path(os.environ.get("CM_DATA_DIR", PROJECT_ROOT / "data"))

# --- whisper.cpp (vendored + built by scripts/setup.sh) ----------------------
WHISPER_DIR = Path(os.environ.get("CM_WHISPER_DIR", PROJECT_ROOT / "vendor" / "whisper.cpp"))
# whisper.cpp renamed the binary main -> whisper-cli; support both.
def _resolve_whisper_cli() -> Path:
    override = os.environ.get("CM_WHISPER_CLI")
    if override:
        return Path(override)
    for candidate in (
        WHISPER_DIR / "build" / "bin" / "whisper-cli",
        WHISPER_DIR / "build" / "bin" / "main",
        WHISPER_DIR / "main",
    ):
        if candidate.exists():
            return candidate
    # default to the modern path even if not built yet (clear error downstream)
    return WHISPER_DIR / "build" / "bin" / "whisper-cli"

WHISPER_CLI = _resolve_whisper_cli()
DEFAULT_MODEL = os.environ.get("CM_WHISPER_MODEL", "base.en")

def model_path(model: str | None = None) -> Path:
    model = model or DEFAULT_MODEL
    return WHISPER_DIR / "models" / f"ggml-{model}.bin"

# --- External binaries -------------------------------------------------------
FFMPEG = os.environ.get("CM_FFMPEG", shutil.which("ffmpeg") or "ffmpeg")
FFPROBE = os.environ.get("CM_FFPROBE", shutil.which("ffprobe") or "ffprobe")
CLAUDE = os.environ.get("CM_CLAUDE", shutil.which("claude") or "claude")

# --- Audio / clip defaults ---------------------------------------------------
AUDIO_SAMPLE_RATE = 16_000  # whisper.cpp requires 16kHz mono
ASPECT_RATIOS = ("9:16", "1:1", "16:9")


def require_tool(path: str | Path, hint: str) -> None:
    """Raise a clear, actionable error if a required local tool is missing."""
    p = Path(path)
    found = p.exists() or shutil.which(str(path)) is not None
    if not found:
        raise FileNotFoundError(f"Required tool not found: {path}\n  → {hint}")
