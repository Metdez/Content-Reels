# Phase 5: Windows Cross-Platform Port — Context

**Gathered:** 2026-06-29
**Status:** Ready for planning
**Mode:** Auto-generated (autonomous, discuss skipped)

<domain>
## Phase Boundary

Make the v1.0 macOS pipeline run end-to-end on Windows 11 with no package manager.
The toolchain is vendored (gitignored) rather than built: static ffmpeg/ffprobe and a
prebuilt whisper.cpp release, plus the whisper model. Code must resolve `.exe` binaries
and Windows fonts, and a `setup.ps1` reproduces the toolchain.
</domain>

<decisions>
## Implementation Decisions

- ffmpeg/ffprobe: BtbN static **full** build (has drawtext/libass) → `vendor/bin/`.
- whisper.cpp: prebuilt `whisper-blas-bin-x64.zip` (v1.9.1) → `vendor/whisper.cpp/build/bin/`.
- Binary resolution order (config.py): env override → PATH → `vendor/bin` → bare name.
- whisper-cli resolution adds `.exe` candidates and an os.name-aware default.
- Fonts: prepend Windows font paths to FONT_CANDIDATES; keep Mac/Linux entries.
- Keep `setup.sh` (Mac) untouched; add `setup.ps1` (Windows) alongside it.
</decisions>

<specifics>
## Success Criteria
1. whisper-cli.exe + ffmpeg/ffprobe.exe resolve via config.py on Windows.
2. Captions render with a real Windows font (no Mac-path crash).
3. setup.ps1 downloads ffmpeg + whisper + model + venv idempotently.
4. pytest green on Windows.
</specifics>
