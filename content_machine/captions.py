"""Caption rendering.

This machine's Homebrew ffmpeg is a stripped build with NO libass/drawtext —
only the `overlay` filter survives. So captions are rendered to transparent PNG
strips with Pillow and composited by ffmpeg `overlay` (time-gated). This is the
default ("overlay" mode): deterministic, low-memory, works with any ffmpeg.

A hyperframes mode is also provided (animated HTML→MOV overlay) for richer
captions when Chrome + RAM are available; render.py falls back to overlay mode
if it fails.

Caption events come from transcript segments, re-timed relative to the clip.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Bold, legible sans-serif candidates across OSes. Windows fonts first when on
# Windows, then macOS, then common Linux paths — first existing wins.
_WINDOWS_FONTS = [
    r"C:\Windows\Fonts\arialbd.ttf",     # Arial Bold
    r"C:\Windows\Fonts\seguisb.ttf",     # Segoe UI Semibold
    r"C:\Windows\Fonts\segoeui.ttf",     # Segoe UI
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\calibrib.ttf",    # Calibri Bold
]
_MAC_FONTS = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/Library/Fonts/Arial.ttf",
]
_LINUX_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
if os.name == "nt":
    FONT_CANDIDATES = _WINDOWS_FONTS + _MAC_FONTS + _LINUX_FONTS
else:
    FONT_CANDIDATES = _MAC_FONTS + _LINUX_FONTS + _WINDOWS_FONTS


def find_font() -> str | None:
    for f in FONT_CANDIDATES:
        if Path(f).exists():
            return f
    return None


def clip_caption_events(segments: list[dict], clip_start: float, clip_end: float) -> list[dict]:
    """Segments overlapping [clip_start, clip_end], re-timed to clip-relative seconds."""
    events = []
    for s in segments:
        if s["end"] <= clip_start or s["start"] >= clip_end:
            continue
        start = max(0.0, s["start"] - clip_start)
        end = min(clip_end, s["end"]) - clip_start
        text = s["text"].strip()
        if text and end > start:
            events.append({"start": start, "end": end, "text": text})
    return events


def _group_words_into_lines(words: list[dict], max_chars: int) -> list[list[dict]]:
    """Greedily group word dicts into display lines under a character budget.

    Mirrors textwrap's greedy line-filling (words are never split), but keeps each
    word's dict so per-word timing/highlighting survives. Empty/whitespace tokens
    are dropped."""
    lines: list[list[dict]] = []
    cur: list[dict] = []
    cur_len = 0
    for w in words:
        token = str(w.get("word", "")).strip()
        if not token:
            continue
        add = len(token) + (1 if cur else 0)
        if cur and cur_len + add > max_chars:
            lines.append(cur)
            cur, cur_len = [w], len(token)
        else:
            cur.append(w)
            cur_len += add
    if cur:
        lines.append(cur)
    return lines


def clip_word_events(segments: list[dict], clip_start: float, clip_end: float,
                     max_chars: int = 24) -> list[dict]:
    """Word-level karaoke events for segments overlapping [clip_start, clip_end].

    For each overlapping segment with per-word timing (``words[]``), the words are
    grouped into display lines and ONE event is emitted per word:
    ``{start, end, text, highlight}`` — ``start``/``end`` are the WORD's clip-relative
    seconds, ``text`` is the full display line the word belongs to, and ``highlight``
    is that word's index within the line (so the caption PNG can accent it).

    A segment with no usable word timing degrades to a single segment-level event
    (text only, no ``highlight``) — i.e. karaoke falls back to a normal caption for
    that segment. Events are returned sorted by ``start``."""
    events: list[dict] = []
    for s in segments:
        if s["end"] <= clip_start or s["start"] >= clip_end:
            continue
        usable = []
        for w in s.get("words") or []:
            try:
                ws, we = float(w["start"]), float(w["end"])
            except (KeyError, TypeError, ValueError):
                continue
            if we <= clip_start or ws >= clip_end:
                continue
            usable.append(w)
        if not usable:                                  # no word timing -> segment fallback
            start = max(0.0, s["start"] - clip_start)
            end = min(clip_end, s["end"]) - clip_start
            text = s["text"].strip()
            if text and end > start:
                events.append({"start": start, "end": end, "text": text})
            continue
        for line_words in _group_words_into_lines(usable, max_chars):
            line_text = " ".join(str(w.get("word", "")).strip() for w in line_words)
            for hi, w in enumerate(line_words):
                ws = max(0.0, float(w["start"]) - clip_start)
                we = min(clip_end, float(w["end"])) - clip_start
                if we <= ws:
                    continue
                events.append({"start": ws, "end": we, "text": line_text, "highlight": hi})
    events.sort(key=lambda e: e["start"])
    return events


# --- Pillow PNG overlays (default) -------------------------------------------
# Karaoke accent color for the currently-spoken word (bright yellow).
KARAOKE_ACCENT = (255, 230, 0, 255)


def wrap_caption(text: str, max_chars: int) -> str:
    return "\n".join(textwrap.wrap(text, width=max_chars)) or text


def fit_caption(draw, text: str, font_path: str | None, width: int, height: int):
    """Pick a font size + wrap so the caption fills a consistent, safe portion of
    the frame in ANY aspect ratio and never overflows the usable width.

    Font size keys off the SHORTER side (min(w,h)) so a tall 9:16, a square 1:1,
    and a wide 16:9 — all 1080 on their short side — get the same perceptual size,
    instead of height-scaling that made 9:16 captions ~2x bigger than 16:9. Text
    wraps to ~86% of the width (the LinkedIn-safe text column) and the size shrinks
    only if a very long caption would still be too tall.
    """
    usable_w = width * 0.86
    base = max(30, round(min(width, height) * 0.052))
    spacing = max(4, round(base * 0.18))
    for font_size in range(base, 23, -3):
        font = (ImageFont.truetype(font_path, font_size) if font_path
                else ImageFont.load_default())
        # average glyph ~0.52*em for this sans; wrap to the usable column
        max_chars = max(8, int(usable_w / (font_size * 0.52)))
        wrapped = wrap_caption(text, max_chars)
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center", spacing=spacing)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if tw <= usable_w and th <= height * 0.30:
            return font, font_size, wrapped, bbox, spacing
    # fallback: smallest tried
    return font, font_size, wrapped, bbox, spacing


def _render_highlight_line(img: Image.Image, draw, text: str, highlight: int,
                           width: int, height: int, font, font_size: int, bbox, spacing) -> None:
    """Draw ``text`` as a single centered line with word ``highlight`` in the accent
    color (the rest white) — same backing box / stroke / bottom position as the plain
    caption. Used for karaoke; words are laid out left-to-right by their advance widths."""
    words = text.split()
    if not 0 <= highlight < len(words):
        highlight = -1                                  # out of range -> no accent
    space_w = draw.textlength(" ", font=font)
    widths = [draw.textlength(w, font=font) for w in words]
    total = sum(widths) + space_w * max(0, len(words) - 1)
    th = bbox[3] - bbox[1]
    x0 = (width - total) / 2
    y = height - th - round(height * 0.09) - bbox[1]    # ~9% bottom safe margin

    pad = round(font_size * 0.45)
    bx0 = max(4, x0 - pad)
    bx1 = min(width - 4, x0 + total + pad)
    draw.rounded_rectangle(
        [bx0, y + bbox[1] - pad, bx1, y + bbox[1] + th + pad],
        radius=pad, fill=(0, 0, 0, 150),
    )
    stroke = max(2, font_size // 16)
    cx = x0
    for i, w in enumerate(words):
        fill = KARAOKE_ACCENT if i == highlight else (255, 255, 255, 255)
        draw.text((cx, y), w, font=font, fill=fill,
                  stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
        cx += widths[i] + space_w


def render_caption_png(text: str, width: int, height: int, out: Path,
                       font_path: str | None = None, highlight: int | None = None) -> Path:
    """Render one full-frame transparent PNG with the caption in the bottom safe area.

    With ``highlight`` set (a 0-based word index), the line is drawn word-by-word with
    that word in the karaoke accent color; the box/stroke/position are unchanged. The
    default (``highlight=None``) path is byte-for-byte the original behavior."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    fp = font_path or find_font()
    font, font_size, wrapped, bbox, spacing = fit_caption(draw, text, fp, width, height)

    if highlight is not None:
        _render_highlight_line(img, draw, text, highlight, width, height,
                               font, font_size, bbox, spacing)
        img.save(out)
        return out

    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (width - tw) / 2 - bbox[0]
    y = height - th - round(height * 0.09) - bbox[1]   # ~9% bottom safe margin

    # semi-opaque rounded backing for legibility on any footage, clamped to frame
    pad = round(font_size * 0.45)
    bx0 = max(4, x + bbox[0] - pad)
    bx1 = min(width - 4, x + bbox[0] + tw + pad)
    draw.rounded_rectangle(
        [bx0, y + bbox[1] - pad, bx1, y + bbox[1] + th + pad],
        radius=pad, fill=(0, 0, 0, 150),
    )
    draw.multiline_text((x, y), wrapped, font=font, fill=(255, 255, 255, 255),
                        align="center", spacing=spacing,
                        stroke_width=max(2, font_size // 16), stroke_fill=(0, 0, 0, 255))
    img.save(out)
    return out


def render_caption_pngs(events: list[dict], width: int, height: int, outdir: Path,
                        font_path: str | None = None) -> list[dict]:
    """Render one PNG per event; return [{png, start, end}] for overlay gating.

    Karaoke events carry a ``highlight`` word index (rendered in the accent color);
    plain events have none and render exactly as before."""
    outdir.mkdir(parents=True, exist_ok=True)
    out = []
    for i, e in enumerate(events):
        png = outdir / f"cap_{i:03d}.png"
        render_caption_png(e["text"], width, height, png, font_path,
                           highlight=e.get("highlight"))
        out.append({"png": png, "start": e["start"], "end": e["end"]})
    return out


# --- hyperframes (optional animated mode) ------------------------------------
def hyperframes_bin() -> str | None:
    local = Path(__file__).resolve().parent.parent / "tools" / "hyperframes" / "node_modules" / ".bin" / "hyperframes"
    if local.exists():
        return str(local)
    return shutil.which("hyperframes")


def hyperframes_available() -> bool:
    return hyperframes_bin() is not None


def build_caption_composition(events: list[dict], width: int, height: int,
                              fps: int, project_dir: Path) -> Path:
    """Scaffold a minimal hyperframes composition project (index.html) for captions.

    Uses hyperframes' player runtime: `data-composition-duration` declares length;
    window.__hyperframes.onFrame(fn) (fallback: getTime()) drives which caption
    shows. Output is rendered to a transparent MOV by the caller.

    Karaoke: events carrying a ``highlight`` word index render that word in the
    accent color (the rest of the line white). NOTE: rendering this composition
    requires Node >= 22 + a real Chrome (hyperframes' headless renderer); where that
    isn't available render.py falls back to the PNG karaoke path, which preserves the
    highlighting. This scaffold is code-complete for capable environments.
    """
    project_dir.mkdir(parents=True, exist_ok=True)
    duration = max((e["end"] for e in events), default=0.0)
    font_size = max(36, round(height * 0.045))
    bottom = round(height * 0.10)
    data = json.dumps(events)
    (project_dir / "index.html").write_text(f"""<!doctype html>
<html><head><meta charset="utf-8">
<body data-composition-duration="{duration}" data-composition-fps="{fps}"
      data-composition-width="{width}" data-composition-height="{height}"
      style="margin:0;width:{width}px;height:{height}px;background:transparent;
             font-family:Arial,Helvetica,sans-serif;overflow:hidden">
  <div id="cap" style="position:absolute;left:6%;right:6%;bottom:{bottom}px;
       text-align:center;color:#fff;font-weight:800;font-size:{font_size}px;
       line-height:1.15;text-shadow:0 0 8px #000,0 3px 6px #000;
       opacity:0;transform:translateY(18px);transition:opacity .15s,transform .15s"></div>
  <script>
    const EVENTS = {data};
    const ACCENT = '#FFE600';
    const cap = document.getElementById('cap');
    function esc(s){{ return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }}
    function frame(t){{
      const e = EVENTS.find(e => t >= e.start && t < e.end);
      if (e) {{
        if (e.highlight != null) {{
          const ws = e.text.split(' ');
          cap.innerHTML = ws.map((w, i) => i === e.highlight
            ? '<span style="color:' + ACCENT + '">' + esc(w) + '</span>' : esc(w)).join(' ');
        }} else {{ cap.textContent = e.text; }}
        cap.style.opacity = 1; cap.style.transform = 'translateY(0)';
      }}
      else {{ cap.style.opacity = 0; cap.style.transform = 'translateY(18px)'; }}
    }}
    const hf = window.__hyperframes;
    if (hf && hf.onFrame) hf.onFrame((s) => frame(s.time != null ? s.time : s));
    else if (hf && hf.getTime) {{ const loop=()=>{{frame(hf.getTime());requestAnimationFrame(loop)}}; loop(); }}
    else {{ const t0=performance.now(); const loop=()=>{{frame((performance.now()-t0)/1000);requestAnimationFrame(loop)}}; loop(); }}
  </script>
</body></html>""")
    return project_dir


def render_hyperframes_overlay(events: list[dict], width: int, height: int,
                               out_path: Path, fps: int = 30, timeout: int = 300) -> Path:
    """Render a transparent caption overlay (.mov) via the hyperframes CLI.

    Raises on failure so render.py can fall back to the Pillow overlay path.
    """
    hf = hyperframes_bin()
    if not hf:
        raise RuntimeError("hyperframes CLI not found")
    project = build_caption_composition(events, width, height, fps, out_path.parent / "hf_proj")
    mov = out_path.with_suffix(".mov")  # MOV => transparency
    cmd = [hf, "render", str(project), "-o", str(mov), "--format", "mov",
           "--fps", str(fps), "-w", "1", "--quiet"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0 or not mov.exists():
        raise RuntimeError(f"hyperframes render failed: {proc.stderr[:400] or proc.stdout[:400]}")
    return mov
