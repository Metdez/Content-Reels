# v4 Hardware-Acceleration Benchmarks

Honest, measured results on the author's Windows machine. Run them yourself with:

```
python scripts/benchmark.py EnlayeParis.mp4 --seconds 30 --start 90
```

The harness renders a clip in all 3 aspect ratios with the detected GPU encoder
vs forced CPU `libx264`, validates every output with ffprobe (codec, dimensions,
audio present, not corrupt), and times CPU transcription.

## Machine

- Windows 11 · Ryzen 9 · **RTX 5060 Laptop GPU** (Blackwell, 8 GB) · driver 591.74 · 16 GB RAM
- ffmpeg **7.1** (pinned — see below) · whisper.cpp v1.9.1 base.en

## Results (2026-06-30)

### Render — GPU NVENC vs CPU x264

| Workload | NVENC | x264 (CPU) | Speedup | Outputs valid |
|---|---|---|---|---|
| 9:16 single, 60 s clip | 7.85 s | 10.68 s | **1.36×** | ✓ |
| 3 aspects, 30 s clip | 7.01 s | 7.57 s | **1.08×** | ✓ (h264, correct dims, audio in all) |
| 9:16 single, 6 s clip | 2.00 s | 1.34 s | 0.67× | ✓ |

**Reading the numbers honestly:**
- The crop/scale (and caption overlay) **filters run on the CPU for both paths** — only the final encode is offloaded. So the render is filter-bound and the encode-only speedup is modest (≈1.1–1.4× on realistic 15–90 s clips).
- **Short clips (<~10 s) can be slower on NVENC** — the GPU encode session has a fixed setup cost that a tiny encode doesn't amortize.
- The steadier practical benefit is that NVENC **frees CPU cores** during render (the machine isn't pegged, the UI stays responsive).
- NVENC is **probed at startup and auto-falls-back to x264** on any failure, so it is purely additive — it never makes rendering break.

### Transcribe — CPU whisper

| Workload | Time | Realtime factor |
|---|---|---|
| base.en, 30 s audio | 3.35 s | **8.9×** |

CPU transcription on the Ryzen 9 is already fast (≈9× realtime), so a ~14-minute
video transcribes in ~1.5 min.

## Decisions these numbers drove

1. **Windows ffmpeg is pinned to 7.1**, not bleeding-edge master. Master's NVENC
   requires NVIDIA driver ≥ 610; driver 591.74 only exposes the older NVENC API,
   so master *fails to init NVENC*. 7.1's NVENC works on 591.74 (verified). The
   runtime probe + CPU fallback covers any residual mismatch.

2. **Windows transcription stays on CPU (BLAS), not GPU.** The only prebuilt CUDA
   whisper (cuBLAS 12.4, whisper.cpp v1.9.1) **detects** the RTX 5060 but has no
   native Blackwell (sm_120) kernels — it PTX-JITs to unoptimized ones and runs
   **~40× slower than CPU** (48 s for 8 s of audio; hangs entirely with flash
   attention on). Native Blackwell whisper needs a from-source CUDA 12.8+ build
   (toolkit install), deferred as out of scope for "dead-simple setup". CPU BLAS
   is already ~9× realtime, so this costs little.

3. **Encode-only, aspects serial.** GPU decode + GPU scaling were deliberately
   skipped (mixing hw-decode with the CPU filtergraph breaks it); the RTX 5060 has
   one NVENC engine so parallel encode sessions buy ~nothing. Parallelizing the 3
   aspects across CPU cores (to cut the filter-bound wall-time) is a possible
   future win but adds concurrency to the job runner — out of scope under the
   "must not break" priority.
