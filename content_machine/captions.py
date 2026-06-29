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
import shutil
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/Library/Fonts/Arial.ttf",
]


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


# --- Pillow PNG overlays (default) -------------------------------------------
def wrap_caption(text: str, max_chars: int) -> str:
    return "\n".join(textwrap.wrap(text, width=max_chars)) or text


def render_caption_png(text: str, width: int, height: int, out: Path,
                       font_path: str | None = None) -> Path:
    """Render one full-frame transparent PNG with the caption near the bottom."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font_size = max(36, round(height * 0.045))
    fp = font_path or find_font()
    font = ImageFont.truetype(fp, font_size) if fp else ImageFont.load_default()

    max_chars = max(12, int(width / (font_size * 0.6)))
    wrapped = wrap_caption(text, max_chars)

    # measure block
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center", spacing=8)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (width - tw) / 2 - bbox[0]
    y = height - th - round(height * 0.10) - bbox[1]

    # semi-opaque rounded backing for legibility on any footage
    pad = round(font_size * 0.4)
    draw.rounded_rectangle(
        [x + bbox[0] - pad, y + bbox[1] - pad, x + bbox[0] + tw + pad, y + bbox[1] + th + pad],
        radius=pad, fill=(0, 0, 0, 140),
    )
    draw.multiline_text((x, y), wrapped, font=font, fill=(255, 255, 255, 255),
                        align="center", spacing=8,
                        stroke_width=max(2, font_size // 18), stroke_fill=(0, 0, 0, 255))
    img.save(out)
    return out


def render_caption_pngs(events: list[dict], width: int, height: int, outdir: Path,
                        font_path: str | None = None) -> list[dict]:
    """Render one PNG per event; return [{png, start, end}] for overlay gating."""
    outdir.mkdir(parents=True, exist_ok=True)
    out = []
    for i, e in enumerate(events):
        png = outdir / f"cap_{i:03d}.png"
        render_caption_png(e["text"], width, height, png, font_path)
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
    const cap = document.getElementById('cap');
    function frame(t){{
      const e = EVENTS.find(e => t >= e.start && t < e.end);
      if (e) {{ cap.textContent = e.text; cap.style.opacity = 1; cap.style.transform = 'translateY(0)'; }}
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
