"""Phase 13 self-checks: encoder selection, profile wiring, and CPU fallback.

No real ffmpeg/GPU needed — probes and runners are stubbed.
"""

import subprocess
from pathlib import Path

from content_machine import hwaccel, render


def test_force_cpu_selects_x264(monkeypatch):
    monkeypatch.setenv("CM_FORCE_CPU", "1")
    hwaccel.reset_probe_cache()
    enc = hwaccel.select_encoder()
    assert enc["key"] == "x264" and enc["codec"] == "libx264"


def test_select_prefers_probed_gpu(monkeypatch):
    monkeypatch.delenv("CM_FORCE_CPU", raising=False)
    monkeypatch.delenv("CM_ENCODER", raising=False)
    monkeypatch.setattr(hwaccel, "_probe", lambda key: key in ("nvenc", "x264"))
    enc = hwaccel.select_encoder(prefer="nvenc")
    assert enc["key"] == "nvenc" and enc["codec"] == "h264_nvenc"


def test_select_falls_back_when_gpu_probe_fails(monkeypatch):
    monkeypatch.delenv("CM_FORCE_CPU", raising=False)
    monkeypatch.delenv("CM_ENCODER", raising=False)
    monkeypatch.setattr(hwaccel, "_probe", lambda key: key == "x264")  # GPU unavailable
    enc = hwaccel.select_encoder()
    assert enc["key"] == "x264"                       # never raises — always usable


def test_select_videotoolbox_on_macos(monkeypatch):
    monkeypatch.delenv("CM_FORCE_CPU", raising=False)
    monkeypatch.delenv("CM_ENCODER", raising=False)
    monkeypatch.setattr(hwaccel.sys, "platform", "darwin")        # pretend macOS
    monkeypatch.setattr(hwaccel, "_probe", lambda key: key in ("videotoolbox", "x264"))
    enc = hwaccel.select_encoder()
    assert enc["key"] == "videotoolbox" and enc["codec"] == "h264_videotoolbox"
    assert "-allow_sw" in enc["args"]                              # SW VT fallback flag present


def test_macos_falls_back_to_x264_when_videotoolbox_unavailable(monkeypatch):
    monkeypatch.delenv("CM_FORCE_CPU", raising=False)
    monkeypatch.delenv("CM_ENCODER", raising=False)
    monkeypatch.setattr(hwaccel.sys, "platform", "darwin")
    monkeypatch.setattr(hwaccel, "_probe", lambda key: key == "x264")  # VT absent (e.g. Intel)
    assert hwaccel.select_encoder()["key"] == "x264"                   # never breaks on Mac


def test_build_render_cmd_defaults_to_x264_but_honors_encoder():
    args = dict(src=Path("s.mp4"), start=0.0, end=5.0, aspect="9:16", x_offset=0.0,
                out=Path("o.mp4"), src_w=1920, src_h=1080)
    base = render.build_render_cmd(**args)
    assert "libx264" in base                          # back-compat default = CPU
    assert "aac" in base and "+faststart" in base

    nv = render.build_render_cmd(**args, encoder=hwaccel.PROFILES["nvenc"])
    assert "h264_nvenc" in nv and "libx264" not in nv  # GPU encode tail swapped in
    assert "aac" in nv and "+faststart" in nv          # audio + faststart preserved


def test_run_encode_falls_back_to_x264_on_gpu_failure(monkeypatch):
    calls = []

    def fake_stream(cmd, log_, desc, **kw):
        calls.append((cmd, desc))
        if "h264_nvenc" in cmd and "fallback" not in desc:
            raise subprocess.CalledProcessError(1, cmd)   # GPU encode dies

    monkeypatch.setattr(render, "stream_run", fake_stream)
    build = lambda e: ["ffmpeg", *e["args"], "out.mp4"]
    used = render._run_encode(build, hwaccel.PROFILES["nvenc"], render.log, "render clip")
    assert used["key"] == "x264"                          # ended up on the CPU path
    assert any("h264_nvenc" in c for c, _ in calls)       # tried GPU first
    assert any("libx264" in c for c, _ in calls)          # then x264
    assert any("fallback" in d for _, d in calls)         # logged as a fallback


def test_run_encode_uses_x264_directly_without_trying_gpu(monkeypatch):
    calls = []
    monkeypatch.setattr(render, "stream_run",
                        lambda cmd, log_, desc, **kw: calls.append(cmd))
    build = lambda e: ["ffmpeg", *e["args"], "out.mp4"]
    used = render._run_encode(build, hwaccel.X264, render.log, "render clip")
    assert used["key"] == "x264" and len(calls) == 1      # one call, no GPU attempt
