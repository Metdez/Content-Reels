"""Phase 3 self-checks: crop math, filtergraph, ffmpeg cmd, caption events + PNG."""

from pathlib import Path

from content_machine import render as r
from content_machine import captions as cap


def test_compute_crop_vertical_from_landscape():
    cw, ch, x, y = r.compute_crop(1920, 1080, "9:16", x_offset=0.0)
    assert ch == 1080
    assert abs(cw - 608) <= 2 and cw % 2 == 0
    assert y == 0


def test_compute_crop_x_offset_shifts_window():
    _, _, x_center, _ = r.compute_crop(1920, 1080, "9:16", 0.0)
    cw_r, _, x_right, _ = r.compute_crop(1920, 1080, "9:16", 1.0)
    _, _, x_left, _ = r.compute_crop(1920, 1080, "9:16", -1.0)
    assert x_left < x_center < x_right
    assert x_left == 0
    assert x_right == 1920 - cw_r


def test_compute_crop_square_and_landscape():
    cw, ch, _, _ = r.compute_crop(1920, 1080, "1:1")
    assert cw == ch == 1080
    cw2, ch2, _, _ = r.compute_crop(1920, 1080, "16:9")
    assert (cw2, ch2) == (1920, 1080)


def test_crop_scale_filter():
    f = r.crop_scale_filter(1920, 1080, "9:16", 0.0)
    assert "crop=" in f and "scale=1080:1920" in f


def test_render_cmd_no_captions_uses_vf_and_input_seek():
    cmd = r.build_render_cmd(Path("s.mp4"), 10.0, 25.0, "1:1", 0.0,
                             Path("o.mp4"), 1920, 1080, png_events=None)
    assert cmd.index("-ss") < cmd.index("-i")          # input seek
    assert "-vf" in cmd and "-filter_complex" not in cmd
    assert "-t" in cmd and "15.000" in cmd             # duration, not endpoint
    assert "libx264" in cmd and "copy" not in cmd      # re-encode


def test_render_cmd_with_captions_builds_gated_overlay_chain():
    pngs = [{"png": Path("a.png"), "start": 0.0, "end": 2.0},
            {"png": Path("b.png"), "start": 2.0, "end": 4.0}]
    cmd = r.build_render_cmd(Path("s.mp4"), 5.0, 12.0, "9:16", 0.0,
                             Path("o.mp4"), 1920, 1080, png_events=pngs)
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert fc.count("overlay=") == 2                   # one per caption
    assert "enable='between(t,0.000,2.000)'" in fc
    assert "[base]" in fc and "scale=1080:1920" in fc
    assert cmd.count("-loop") == 2                      # one looped image input each


def test_clip_caption_events_retimes_relative_to_clip():
    segs = [
        {"start": 0, "end": 5, "text": "before clip"},
        {"start": 22, "end": 26, "text": "inside one"},
        {"start": 26, "end": 30, "text": "inside two"},
        {"start": 40, "end": 45, "text": "after clip"},
    ]
    events = cap.clip_caption_events(segs, 22, 30)
    assert [e["text"] for e in events] == ["inside one", "inside two"]
    assert events[0]["start"] == 0.0 and events[0]["end"] == 4.0


def test_render_caption_png_writes_transparent_image(tmp_path):
    from PIL import Image
    out = cap.render_caption_png("Hello world this is a caption", 1080, 1920, tmp_path / "c.png")
    img = Image.open(out)
    assert img.size == (1080, 1920)
    assert img.mode == "RGBA"
    assert img.getextrema()[3][1] > 0                  # has some opaque pixels (text/box)


def test_wrap_caption_breaks_long_text():
    wrapped = cap.wrap_caption("one two three four five six seven", max_chars=10)
    assert "\n" in wrapped
