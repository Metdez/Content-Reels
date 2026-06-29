# Phase 5: Windows Cross-Platform Port — Summary

**Status:** Complete ✅
**Completed:** 2026-06-29

## What shipped

The v1.0 macOS pipeline now runs end-to-end on Windows 11 with no package manager.

- **Toolchain (vendored, gitignored):** `scripts/setup.ps1` downloads a static **full** BtbN
  ffmpeg/ffprobe → `vendor/bin/`, prebuilt whisper.cpp `whisper-blas-bin-x64` (v1.9.1) →
  `vendor/whisper.cpp/build/bin/`, and `ggml-base.en.bin` → `vendor/whisper.cpp/models/`,
  then creates `.venv` and installs the package.
- **OS-agnostic binary resolution** (`config.py`): whisper-cli resolves `.exe`/`main.exe`
  variants; `_resolve_binary()` does env → PATH → `vendor/bin` → bare-name for ffmpeg/ffprobe/claude.
- **Fonts** (`captions.py`): Windows fonts (Arial Bold, Segoe UI, Calibri) added and preferred
  on `os.name == "nt"`, with the Mac/Linux lists retained as fallback.
- **UTF-8 hardening:** the app prints/logs Unicode glyphs (→ ✓ ✗ ▶ ★ 📜). Forced UTF-8 on
  stdio at import (`__init__.py`) and on all file handlers + subprocess decode paths
  (`logging_setup.py`, `transcribe.py`, `render.py`, `select.py`) — fixes the cp1252
  `UnicodeEncodeError` that crashed the CLI and logging on Windows.
- **Test portability:** one test hardcoded a POSIX path; made it OS-agnostic.

## Verified live (Windows 11, real binaries)

- `pytest` → **28 passed**.
- 60s slice of `EnlayeParis.mp4`: ingest → transcribe (base.en, 31.6s) → **18 segments**.
- `select` via `claude.CMD` subprocess → **2 real clips** with good titles (subscription OAuth path works).
- `render` → 2 clips × {9:16, 1:1, 16:9} with overlay captions; **all 6 outputs carry an aac audio stream** (ffprobe-verified).

## Success criteria

1. ✅ whisper-cli.exe + ffmpeg/ffprobe.exe resolve via config.py
2. ✅ Captions render with a real Windows font (Arial Bold)
3. ✅ setup.ps1 reproduces the toolchain idempotently
4. ✅ pytest green (28 passed)
