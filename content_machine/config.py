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

# Vendored binaries live here on every OS (gitignored). On Windows, setup.ps1
# drops ffmpeg/ffprobe here; on macOS setup.sh uses Homebrew + PATH instead.
VENDOR_BIN = PROJECT_ROOT / "vendor" / "bin"

# --- Local storage -----------------------------------------------------------
DATA_DIR = Path(os.environ.get("CM_DATA_DIR", PROJECT_ROOT / "data"))

# --- whisper.cpp (vendored + built by scripts/setup.{sh,ps1}) ----------------
WHISPER_DIR = Path(os.environ.get("CM_WHISPER_DIR", PROJECT_ROOT / "vendor" / "whisper.cpp"))
# whisper.cpp renamed the binary main -> whisper-cli; support both, and the
# Windows .exe variants from the prebuilt release zips.
def _resolve_whisper_cli() -> Path:
    override = os.environ.get("CM_WHISPER_CLI")
    if override:
        return Path(override)
    build_bin = WHISPER_DIR / "build" / "bin"
    for candidate in (
        build_bin / "whisper-cli.exe",
        build_bin / "main.exe",
        build_bin / "whisper-cli",
        build_bin / "main",
        WHISPER_DIR / "whisper-cli.exe",
        WHISPER_DIR / "main.exe",
        WHISPER_DIR / "main",
    ):
        if candidate.exists():
            return candidate
    # default to the modern path even if not built yet (clear error downstream)
    return build_bin / ("whisper-cli.exe" if os.name == "nt" else "whisper-cli")

WHISPER_CLI = _resolve_whisper_cli()
DEFAULT_MODEL = os.environ.get("CM_WHISPER_MODEL", "base.en")

def model_path(model: str | None = None) -> Path:
    model = model or DEFAULT_MODEL
    return WHISPER_DIR / "models" / f"ggml-{model}.bin"

# --- External binaries -------------------------------------------------------
def _resolve_binary(name: str, env: str) -> str:
    """env override → PATH → vendored vendor/bin → bare name (clear error later)."""
    override = os.environ.get(env)
    if override:
        return override
    found = shutil.which(name)
    if found:
        return found
    exe = name + (".exe" if os.name == "nt" else "")
    vendored = VENDOR_BIN / exe
    if vendored.exists():
        return str(vendored)
    return name

FFMPEG = _resolve_binary("ffmpeg", "CM_FFMPEG")
FFPROBE = _resolve_binary("ffprobe", "CM_FFPROBE")
CLAUDE = _resolve_binary("claude", "CM_CLAUDE")

# --- Audio / clip defaults ---------------------------------------------------
AUDIO_SAMPLE_RATE = 16_000  # whisper.cpp requires 16kHz mono
ASPECT_RATIOS = ("9:16", "1:1", "16:9")


def ffmpeg_hint() -> str:
    """Platform-aware install hint for ffmpeg/ffprobe (VAL-06)."""
    if os.name == "nt":
        return ("Install ffmpeg: run scripts/setup.ps1 "
                "(drops vendored ffmpeg/ffprobe into vendor/bin)")
    return "Install ffmpeg: brew install ffmpeg"


def whisper_hint() -> str:
    """Platform-aware build hint for whisper.cpp (VAL-06)."""
    if os.name == "nt":
        return ("Build whisper.cpp: run scripts/setup.ps1 "
                "(clones + builds vendor/whisper.cpp)")
    return "Build whisper.cpp: bash scripts/setup.sh (clones + builds vendor/whisper.cpp)"


def require_tool(path: str | Path, hint: str) -> None:
    """Raise a clear, actionable error if a required local tool is missing."""
    p = Path(path)
    found = p.exists() or shutil.which(str(path)) is not None
    if not found:
        raise FileNotFoundError(f"Required tool not found: {path}\n  → {hint}")
