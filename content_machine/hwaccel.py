"""GPU-accelerated video ENCODE selection with a structurally-safe CPU fallback.

Only the final video encode is offloaded to the GPU — decode and every filter
(crop / scale / caption overlay) stay on the CPU, because mixing hw-decode with
sw-filters breaks the filtergraph. We probe the candidate GPU encoders ONCE with
a tiny lavfi null-encode; if a probe fails (no GPU, wrong driver, busy engine)
we fall back to `libx264`, so a missing or incompatible GPU is a non-event, not
a crash. Aspect ratios are encoded serially upstream (a consumer GPU has one
encode engine — parallel buys little and risks session exhaustion).

Quality is tuned to ≈ `libx264 -preset veryfast -crf 20`:
  - NVENC (Windows):      h264_nvenc -preset p5 -rc vbr -cq 21
  - VideoToolbox (macOS): h264_videotoolbox -q:v 62 -allow_sw 1
  - x264 (fallback):      libx264 -preset veryfast -crf 20

Override with env:
  CM_ENCODER=nvenc|videotoolbox|x264   force a specific encoder (still probed)
  CM_FORCE_CPU=1                       force the x264 path (e.g. A/B benchmarks)
"""

from __future__ import annotations

import os
import subprocess
import sys

from . import config
from .logging_setup import get_logger

log = get_logger(__name__)

# yuv420p everywhere — our filtered frames are 8-bit 4:2:0; do not switch to 10-bit.
_X264_ARGS = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]

# Each profile is the ffmpeg "-c:v … " ENCODE tail (audio + faststart are added by
# the caller). `key` is the stable selector; `codec` is the ffmpeg encoder name.
PROFILES: dict[str, dict] = {
    "nvenc": {
        "key": "nvenc", "codec": "h264_nvenc",
        "args": ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr",
                 "-cq", "21", "-b:v", "0", "-pix_fmt", "yuv420p"],
    },
    "videotoolbox": {
        "key": "videotoolbox", "codec": "h264_videotoolbox",
        "args": ["-c:v", "h264_videotoolbox", "-q:v", "62", "-b:v", "0",
                 "-allow_sw", "1", "-pix_fmt", "yuv420p"],
    },
    "x264": {"key": "x264", "codec": "libx264", "args": list(_X264_ARGS)},
}

X264 = PROFILES["x264"]  # the always-available fallback profile


def _platform_order() -> list[str]:
    """Encoder preference for this OS, GPU first then the CPU fallback."""
    if sys.platform.startswith("win"):
        return ["nvenc", "x264"]
    if sys.platform == "darwin":
        return ["videotoolbox", "x264"]
    return ["nvenc", "x264"]               # linux: try NVENC, else CPU


# cache the probe verdict per encoder key so we shell out to ffmpeg at most once
_probe_cache: dict[str, bool] = {}


def _probe(key: str) -> bool:
    """True if `key`'s encoder actually initializes on this machine.

    libx264 is always available. GPU encoders run a ~0.1s lavfi null-encode and
    the exit code is the verdict (0 = usable). A nonzero exit — `No NVENC capable
    devices`, `Driver does not support the required nvenc API version`,
    `Cannot load nvcuda.dll`, etc. — means fall back.
    """
    if key in _probe_cache:
        return _probe_cache[key]
    prof = PROFILES.get(key)
    if prof is None:
        return False
    if prof["codec"] == "libx264":
        _probe_cache[key] = True
        return True
    cmd = [config.FFMPEG, "-hide_banner", "-loglevel", "error",
           "-f", "lavfi", "-i", "color=c=black:s=256x256:r=1:d=0.1",
           *prof["args"], "-frames:v", "1", "-f", "null", "-"]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30)
        ok = p.returncode == 0
        if not ok:
            log.info("hwaccel: %s probe unavailable — %s", key,
                     (p.stderr or "").strip().splitlines()[-1:] or "nonzero exit")
    except Exception as e:                  # ffmpeg missing, timeout, etc.
        ok = False
        log.info("hwaccel: %s probe error — %s", key, e)
    _probe_cache[key] = ok
    return ok


def select_encoder(prefer: str | None = None, force_cpu: bool | None = None) -> dict:
    """Return the best usable encoder profile for this machine.

    Resolution order: explicit `prefer`/`CM_ENCODER` → platform GPU → x264. Any
    GPU choice is still probed; a failed probe falls through to the next
    candidate, guaranteeing a usable profile (x264 in the worst case). The result
    carries `key`, `codec`, and the ffmpeg `args` tail.
    """
    if force_cpu is None:
        force_cpu = os.environ.get("CM_FORCE_CPU", "").lower() in ("1", "true", "yes")
    if force_cpu:
        return X264
    env_pref = os.environ.get("CM_ENCODER") or None
    prefer = prefer or env_pref
    order = ([prefer] if prefer in PROFILES else []) + _platform_order()
    seen = set()
    for key in order:
        if key in seen:
            continue
        seen.add(key)
        if _probe(key):
            prof = PROFILES[key]
            log.info("hwaccel: encode via %s (%s)", key, prof["codec"])
            return prof
    log.info("hwaccel: no GPU encoder usable — falling back to x264 (CPU)")
    return X264


def reset_probe_cache() -> None:
    """Drop cached probe verdicts (tests / after vendoring a new ffmpeg)."""
    _probe_cache.clear()
