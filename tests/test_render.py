"""Phase 3 self-checks: crop math, filtergraph, ffmpeg cmd, caption events + PNG."""

from pathlib import Path

from content_machine import captions as cap
from content_machine import render as r


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


# --- v3: zoom + vertical pan + per-aspect transforms -------------------------

def test_compute_crop_zoom_shrinks_window_both_axes():
    cw0, ch0, _, _ = r.compute_crop(1920, 1080, "9:16", 0.0)              # zoom 1.0
    cw2, ch2, _, _ = r.compute_crop(1920, 1080, "9:16", 0.0, zoom=2.0)    # 2x tighter
    assert cw2 < cw0 and ch2 < ch0
    assert abs(cw2 - cw0 / 2) <= 2 and abs(ch2 - ch0 / 2) <= 2


def test_compute_crop_y_offset_pans_when_zoomed():
    _, _, _, y_top = r.compute_crop(1920, 1080, "9:16", 0.0, zoom=2.0, y_offset=-1.0)
    _, _, _, y_mid = r.compute_crop(1920, 1080, "9:16", 0.0, zoom=2.0, y_offset=0.0)
    _, ch, _, y_bot = r.compute_crop(1920, 1080, "9:16", 0.0, zoom=2.0, y_offset=1.0)
    assert y_top < y_mid < y_bot
    assert y_top == 0
    assert y_bot == 1080 - ch


def test_compute_crop_y_offset_is_noop_without_vertical_slack():
    # 9:16 from 16:9 at zoom 1.0 is full-height — no vertical slack to pan
    for yo in (-1.0, 0.0, 1.0):
        assert r.compute_crop(1920, 1080, "9:16", 0.0, 1.0, yo)[3] == 0


def test_normalize_transforms_backcompat_and_clamp():
    tf = r.normalize_transforms(None, x_offset=0.5)
    assert set(tf) == set(r.config.ASPECT_RATIOS)
    assert tf["9:16"] == {"zoom": 1.0, "x": 0.5, "y": 0.0}     # legacy x_offset seeded
    tf2 = r.normalize_transforms({"1:1": {"zoom": 1.8, "y": -0.3}})
    assert tf2["1:1"]["zoom"] == 1.8 and tf2["1:1"]["y"] == -0.3
    assert tf2["9:16"]["zoom"] == 1.0                           # untouched aspect = default
    tf3 = r.normalize_transforms({"9:16": {"zoom": 0.5, "x": 5, "y": -9}})
    assert tf3["9:16"] == {"zoom": 1.0, "x": 1.0, "y": -1.0}    # zoom>=1, x/y in [-1,1]


def test_build_render_cmd_threads_zoom_and_y_into_crop():
    cmd = r.build_render_cmd(Path("s.mp4"), 0.0, 5.0, "9:16", 0.0,
                             Path("o.mp4"), 1920, 1080, zoom=2.0, y_offset=1.0)
    vf = cmd[cmd.index("-vf") + 1]
    assert "crop=304:540:808:540" in vf and "scale=1080:1920" in vf


# --- v3: editor audio (mute / volume) ----------------------------------------

def test_render_cmd_mute_drops_audio():
    cmd = r.build_render_cmd(Path("s.mp4"), 0.0, 5.0, "1:1", 0.0,
                             Path("o.mp4"), 1920, 1080, mute=True)
    assert "-an" in cmd and "-c:a" not in cmd and "0:a?" not in cmd


def test_render_cmd_volume_no_captions_uses_af():
    cmd = r.build_render_cmd(Path("s.mp4"), 0.0, 5.0, "1:1", 0.0,
                             Path("o.mp4"), 1920, 1080, volume=1.5)
    assert "0:a?" in cmd and "-af" in cmd
    af = cmd[cmd.index("-af") + 1]
    assert "volume=1.500" in af and "loudnorm" in af   # scale then normalize loudness


def test_render_cmd_loudnorm_applied_without_volume():
    cmd = r.build_render_cmd(Path("s.mp4"), 0.0, 5.0, "1:1", 0.0,
                             Path("o.mp4"), 1920, 1080)
    assert "loudnorm" in cmd[cmd.index("-af") + 1]      # every clip is normalized


def test_render_cmd_volume_with_captions_folds_into_filtergraph():
    pngs = [{"png": Path("a.png"), "start": 0.0, "end": 2.0}]
    cmd = r.build_render_cmd(Path("s.mp4"), 0.0, 5.0, "9:16", 0.0,
                             Path("o.mp4"), 1920, 1080, png_events=pngs, volume=0.5)
    fc = cmd[cmd.index("-filter_complex") + 1]
    assert "[0:a]volume=0.500,loudnorm" in fc      # scale + normalize inside the graph
    assert "[outa]" in cmd and "-af" not in cmd   # -af is illegal alongside -filter_complex


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
