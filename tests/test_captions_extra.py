"""QA-10: characterization tests for the untested parts of ``content_machine.captions``.

Covers the auto-size/wrap logic (``fit_caption``), font discovery (``find_font``),
batch PNG generation (``render_caption_pngs``), and the optional hyperframes path
(``hyperframes_bin`` / ``hyperframes_available`` / ``build_caption_composition`` /
``render_hyperframes_overlay``). The subprocess + binary lookup are stubbed so no
real hyperframes/Chrome run happens. PIL is used for real (it is fast).

These pin CURRENT behavior — they are not a spec. ``clip_caption_events``,
``render_caption_png`` and ``wrap_caption`` are already covered by test_render.py.
"""

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from content_machine import captions as cap


def _make_draw(w: int, h: int) -> ImageDraw.ImageDraw:
    return ImageDraw.Draw(Image.new("RGBA", (w, h), (0, 0, 0, 0)))


# --- find_font ---------------------------------------------------------------

def test_find_font_real_machine_returns_existing_path_or_none():
    fp = cap.find_font()
    assert fp is None or Path(fp).exists()


def test_find_font_first_existing_candidate_wins(tmp_path, monkeypatch):
    real = tmp_path / "real.ttf"
    real.write_bytes(b"\x00")
    missing_before = tmp_path / "missing_before.ttf"
    other_after = tmp_path / "other_after.ttf"
    monkeypatch.setattr(cap, "FONT_CANDIDATES",
                        [str(missing_before), str(real), str(other_after)])
    assert cap.find_font() == str(real)


def test_find_font_returns_none_when_no_candidate_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(cap, "FONT_CANDIDATES",
                        [str(tmp_path / "a.ttf"), str(tmp_path / "b.ttf")])
    assert cap.find_font() is None


# --- fit_caption -------------------------------------------------------------

def test_fit_caption_returns_tuple_and_base_size_for_short_text():
    draw = _make_draw(1080, 1920)
    fp = cap.find_font()
    font, size, wrapped, bbox, spacing = cap.fit_caption(draw, "Short caption", fp, 1080, 1920)
    assert size == 56                      # max(30, round(min(1080,1920) * 0.052))
    assert isinstance(size, int)
    assert isinstance(wrapped, str) and wrapped == "Short caption"
    assert len(bbox) == 4
    assert spacing == 10                   # max(4, round(56 * 0.18))
    assert font is not None


def test_fit_caption_shrinks_and_wraps_long_text():
    draw = _make_draw(1080, 1920)
    fp = cap.find_font()
    _, short_size, _, _, _ = cap.fit_caption(draw, "Hi", fp, 1080, 1920)
    _, long_size, long_wrapped, _, _ = cap.fit_caption(draw, "word " * 80, fp, 1080, 1920)
    assert long_size < short_size          # a long caption forces the font down
    assert "\n" in long_wrapped            # ...and wraps across multiple lines


def test_fit_caption_falls_back_to_smallest_tried_size():
    draw = _make_draw(1080, 1920)
    fp = cap.find_font()
    # text that can never satisfy the height budget at any tried size -> fallback
    _, size, _, _, _ = cap.fit_caption(draw, "word " * 500, fp, 1080, 1920)
    assert size == 26                      # smallest value in range(56, 23, -3)


# --- render_caption_pngs -----------------------------------------------------

def test_render_caption_pngs_writes_one_png_per_event(tmp_path):
    events = [
        {"start": 0.0, "end": 2.0, "text": "first caption"},
        {"start": 2.0, "end": 4.0, "text": "second caption"},
        {"start": 4.0, "end": 6.5, "text": "third"},
    ]
    outdir = tmp_path / "caps"
    out = cap.render_caption_pngs(events, 540, 960, outdir)

    assert outdir.is_dir()
    assert len(out) == len(events)
    for i, item in enumerate(out):
        assert item["png"] == outdir / f"cap_{i:03d}.png"
        assert item["png"].exists()
        assert item["start"] == events[i]["start"]
        assert item["end"] == events[i]["end"]

    img = Image.open(out[0]["png"])
    assert img.size == (540, 960)
    assert img.mode == "RGBA"


def test_render_caption_pngs_empty_events_still_creates_dir(tmp_path):
    outdir = tmp_path / "empty"
    out = cap.render_caption_pngs([], 540, 960, outdir)
    assert out == []
    assert outdir.is_dir()


# --- clip_word_events (karaoke event builder, CAPS-01) -----------------------

def _seg(start, end, text, words=None):
    s = {"start": start, "end": end, "text": text}
    if words is not None:
        s["words"] = words
    return s


def _words(start, names, step=0.5):
    """Build contiguous word dicts starting at `start`, each `step` long."""
    out, t = [], start
    for w in names:
        out.append({"word": w, "start": round(t, 3), "end": round(t + step, 3)})
        t += step
    return out


def test_clip_word_events_one_event_per_word_clip_relative_with_highlight():
    segs = [_seg(10.0, 12.0, "alpha beta gamma",
                 _words(10.0, ["alpha", "beta", "gamma"]))]
    events = cap.clip_word_events(segs, 10.0, 14.0, max_chars=100)  # one line
    assert len(events) == 3                                  # one event per word
    assert [e["highlight"] for e in events] == [0, 1, 2]     # accent walks the line
    assert all(e["text"] == "alpha beta gamma" for e in events)
    # clip-relative times: first word at 10.0 -> 0.0
    assert events[0]["start"] == 0.0 and events[0]["end"] == 0.5
    assert events[1]["start"] == 0.5
    # sorted by start
    assert [e["start"] for e in events] == sorted(e["start"] for e in events)


def test_clip_word_events_wraps_into_lines_with_per_line_highlight():
    names = ["one", "two", "three", "four", "five"]
    segs = [_seg(0.0, 5.0, " ".join(names), _words(0.0, names))]
    # small char budget forces multiple display lines; highlight is per-line index
    events = cap.clip_word_events(segs, 0.0, 10.0, max_chars=8)
    # more than one distinct line of text
    assert len({e["text"] for e in events}) >= 2
    # highlight resets to 0 at the start of each new line
    first_of_each_line = {}
    for e in events:
        first_of_each_line.setdefault(e["text"], e["highlight"])
    assert set(first_of_each_line.values()) == {0}


def test_clip_word_events_segment_fallback_when_no_words():
    segs = [_seg(10.0, 13.0, "no word timing here", words=None),
            _seg(13.0, 15.0, "this one has words", _words(13.0, ["this", "one"]))]
    events = cap.clip_word_events(segs, 10.0, 16.0)
    fallback = events[0]
    assert "highlight" not in fallback                       # segment-level, no accent
    assert fallback["text"] == "no word timing here"
    assert fallback["start"] == 0.0 and fallback["end"] == 3.0
    # the word-timed segment still produced per-word events with highlight
    assert any("highlight" in e for e in events[1:])


# --- karaoke PNG rendering ---------------------------------------------------

def test_render_caption_pngs_karaoke_highlights_each_word(tmp_path):
    events = [
        {"start": 0.0, "end": 0.5, "text": "red green blue", "highlight": 0},
        {"start": 0.5, "end": 1.0, "text": "red green blue", "highlight": 1},
        {"start": 1.0, "end": 1.5, "text": "red green blue", "highlight": 2},
    ]
    outdir = tmp_path / "kara"
    out = cap.render_caption_pngs(events, 1080, 1920, outdir)
    assert len(out) == 3
    for item in out:
        assert item["png"].exists()
    # each PNG must contain the accent color somewhere (the highlighted word)
    accent = cap.KARAOKE_ACCENT[:3]
    for item in out:
        img = Image.open(item["png"]).convert("RGBA")
        colors = {c[:3] for _, c in img.getcolors(maxcolors=1 << 20)}
        assert accent in colors, "expected the karaoke accent color in the frame"


def test_render_caption_png_highlight_differs_from_plain(tmp_path):
    plain = cap.render_caption_png("alpha beta gamma", 1080, 1920, tmp_path / "plain.png")
    hi = cap.render_caption_png("alpha beta gamma", 1080, 1920, tmp_path / "hi.png", highlight=1)
    accent = cap.KARAOKE_ACCENT[:3]
    plain_colors = {c[:3] for _, c in Image.open(plain).convert("RGBA").getcolors(1 << 20)}
    hi_colors = {c[:3] for _, c in Image.open(hi).convert("RGBA").getcolors(1 << 20)}
    assert accent not in plain_colors                        # plain path unchanged: no accent
    assert accent in hi_colors                               # highlight path adds the accent


# --- hyperframes_bin / hyperframes_available ---------------------------------

def test_hyperframes_bin_prefers_local_install(tmp_path, monkeypatch):
    fake_pkg = tmp_path / "content_machine"
    fake_pkg.mkdir()
    monkeypatch.setattr(cap, "__file__", str(fake_pkg / "captions.py"))
    expected = (Path(str(fake_pkg / "captions.py")).resolve().parent.parent
                / "tools" / "hyperframes" / "node_modules" / ".bin" / "hyperframes")
    expected.parent.mkdir(parents=True)
    expected.write_text("#!/bin/sh\n")
    # even when PATH also has one, the bundled local install must win
    monkeypatch.setattr(cap.shutil, "which", lambda name: "/usr/local/bin/hyperframes")
    assert cap.hyperframes_bin() == str(expected)


def test_hyperframes_bin_falls_back_to_path_lookup(tmp_path, monkeypatch):
    fake_pkg = tmp_path / "content_machine"
    fake_pkg.mkdir()
    monkeypatch.setattr(cap, "__file__", str(fake_pkg / "captions.py"))  # no local tools/ dir
    monkeypatch.setattr(cap.shutil, "which", lambda name: "/usr/local/bin/hyperframes")
    assert cap.hyperframes_bin() == "/usr/local/bin/hyperframes"


def test_hyperframes_bin_none_when_not_found_anywhere(tmp_path, monkeypatch):
    fake_pkg = tmp_path / "content_machine"
    fake_pkg.mkdir()
    monkeypatch.setattr(cap, "__file__", str(fake_pkg / "captions.py"))
    monkeypatch.setattr(cap.shutil, "which", lambda name: None)
    assert cap.hyperframes_bin() is None


def test_hyperframes_available_tracks_bin(monkeypatch):
    monkeypatch.setattr(cap, "hyperframes_bin", lambda: None)
    assert cap.hyperframes_available() is False
    monkeypatch.setattr(cap, "hyperframes_bin", lambda: "/some/path/hyperframes")
    assert cap.hyperframes_available() is True


# --- build_caption_composition -----------------------------------------------

def test_build_caption_composition_scaffolds_expected_html(tmp_path):
    events = [
        {"start": 0.0, "end": 2.0, "text": "Hello there"},
        {"start": 2.0, "end": 4.0, "text": "Second line"},
    ]
    proj = tmp_path / "comp"
    result = cap.build_caption_composition(events, 1080, 1920, 30, proj)

    assert result == proj
    html = (proj / "index.html").read_text()
    assert 'data-composition-duration="4.0"' in html       # max event end
    assert 'data-composition-fps="30"' in html
    assert 'data-composition-width="1080"' in html
    assert 'data-composition-height="1920"' in html
    assert "Hello there" in html and "Second line" in html  # events embedded as JSON
    assert "font-size:86px" in html                         # max(36, round(1920 * 0.045))
    assert "bottom:192px" in html                           # round(1920 * 0.10)


def test_build_caption_composition_supports_word_highlight(tmp_path):
    """CAPS-02: karaoke events (with a `highlight` index) scaffold HTML that wraps the
    current word in the accent color. Code-complete for Node>=22+Chrome boxes."""
    events = [{"start": 0.0, "end": 0.5, "text": "hello world", "highlight": 1}]
    proj = tmp_path / "kara_comp"
    cap.build_caption_composition(events, 1080, 1920, 30, proj)
    html = (proj / "index.html").read_text()
    assert "e.highlight" in html                            # highlight branch present
    assert "#FFE600" in html                                # accent color
    assert '"highlight": 1' in html or '"highlight":1' in html  # event embedded


def test_build_caption_composition_empty_events_zero_duration(tmp_path):
    proj = tmp_path / "empty_comp"
    result = cap.build_caption_composition([], 720, 1280, 24, proj)
    assert result == proj
    html = (proj / "index.html").read_text()
    assert 'data-composition-duration="0.0"' in html        # default when no events
    assert 'data-composition-fps="24"' in html
    assert "const EVENTS = [];" in html


# --- render_hyperframes_overlay (subprocess stubbed) -------------------------

class _FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_render_hyperframes_overlay_raises_without_bin(tmp_path, monkeypatch):
    monkeypatch.setattr(cap, "hyperframes_bin", lambda: None)
    with pytest.raises(RuntimeError, match="hyperframes CLI not found"):
        cap.render_hyperframes_overlay(
            [{"start": 0.0, "end": 1.0, "text": "x"}], 1080, 1920, tmp_path / "o.mp4")


def test_render_hyperframes_overlay_success_builds_cmd_and_returns_mov(tmp_path, monkeypatch):
    monkeypatch.setattr(cap, "hyperframes_bin", lambda: "/fake/bin/hyperframes")
    captured = {}

    def fake_run(cmd, capture_output=False, text=False, timeout=None):
        captured["cmd"] = cmd
        captured["timeout"] = timeout
        Path(cmd[cmd.index("-o") + 1]).write_text("MOV")  # simulate the rendered output
        return _FakeProc(returncode=0)

    monkeypatch.setattr(cap.subprocess, "run", fake_run)
    events = [{"start": 0.0, "end": 2.0, "text": "Hi"}]
    out_path = tmp_path / "overlay.mp4"
    result = cap.render_hyperframes_overlay(events, 1080, 1920, out_path, fps=30)

    assert result == out_path.with_suffix(".mov")
    assert result.exists()

    cmd = captured["cmd"]
    assert cmd[0] == "/fake/bin/hyperframes" and cmd[1] == "render"
    assert cmd[cmd.index("--format") + 1] == "mov"
    assert cmd[cmd.index("--fps") + 1] == "30"
    assert cmd[cmd.index("-w") + 1] == "1"
    assert "--quiet" in cmd
    assert captured["timeout"] == 300                       # default timeout
    # the composition was scaffolded next to the output
    assert (out_path.parent / "hf_proj" / "index.html").exists()


def test_render_hyperframes_overlay_raises_on_nonzero_returncode(tmp_path, monkeypatch):
    monkeypatch.setattr(cap, "hyperframes_bin", lambda: "/fake/bin/hyperframes")

    def fake_run(cmd, capture_output=False, text=False, timeout=None):
        return _FakeProc(returncode=1, stderr="explode")    # no output file produced

    monkeypatch.setattr(cap.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="hyperframes render failed"):
        cap.render_hyperframes_overlay(
            [{"start": 0.0, "end": 1.0, "text": "x"}], 1080, 1920, tmp_path / "o.mp4")


def test_render_hyperframes_overlay_raises_when_output_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(cap, "hyperframes_bin", lambda: "/fake/bin/hyperframes")

    def fake_run(cmd, capture_output=False, text=False, timeout=None):
        return _FakeProc(returncode=0)                      # success code, but no .mov

    monkeypatch.setattr(cap.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="hyperframes render failed"):
        cap.render_hyperframes_overlay(
            [{"start": 0.0, "end": 1.0, "text": "x"}], 1080, 1920, tmp_path / "o.mp4")
