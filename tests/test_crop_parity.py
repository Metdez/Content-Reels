"""CROP-02: golden-vector parity between the shared JS crop math and Python.

The frontend crop math lives in content_machine/static/crop.js (window.CMCrop)
and MUST mirror render.compute_crop EXACTLY. This test generates a grid of
inputs, computes the crop in Python, runs crop.js's computeCrop in Node over the
same inputs, and asserts every (x, y, w, h) matches to the integer.

Skipped when `node` is unavailable (the parity guarantee is enforced in CI,
which installs Node before running tests).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from content_machine import render as r

CROP_JS = Path(__file__).resolve().parents[1] / "content_machine" / "static" / "crop.js"

# Node harness: require crop.js (path via argv to dodge Windows backslash escaping),
# read the vector list from stdin (JSON), print JS computeCrop results (JSON).
_HARNESS = r"""
const { computeCrop } = require(process.argv[2]);
let raw = "";
process.stdin.on("data", (d) => (raw += d));
process.stdin.on("end", () => {
  const vecs = JSON.parse(raw);
  const out = vecs.map(([sw, sh, aspect, x, zoom, y]) => {
    const c = computeCrop(sw, sh, aspect, x, zoom, y);
    return { x: c.x, y: c.y, w: c.w, h: c.h };
  });
  process.stdout.write(JSON.stringify(out));
});
"""

SRC_DIMS = [(1920, 1080), (1080, 1920), (1280, 720), (1000, 1000)]
ASPECTS = ["9:16", "1:1", "16:9"]
ZOOMS = [1.0, 1.5, 2.0, 3.0]
XS = [-1.0, -0.3, 0.0, 0.4, 1.0]
YS = [-1.0, 0.0, 0.5, 1.0]


def _vectors() -> list[tuple]:
    vecs = []
    for sw, sh in SRC_DIMS:
        for aspect in ASPECTS:
            for zoom in ZOOMS:
                for x in XS:
                    for y in YS:
                        vecs.append((sw, sh, aspect, x, zoom, y))
    return vecs


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_crop_js_matches_python_exactly():
    assert CROP_JS.exists(), f"missing {CROP_JS}"
    vecs = _vectors()

    # Python golden: compute_crop returns (crop_w, crop_h, x, y).
    py = []
    for sw, sh, aspect, x, zoom, y in vecs:
        cw, ch, cx, cy = r.compute_crop(sw, sh, aspect, x_offset=x, zoom=zoom, y_offset=y)
        py.append({"x": cx, "y": cy, "w": cw, "h": ch})

    # JS via Node.
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(_HARNESS)
        harness = fh.name
    try:
        proc = subprocess.run(
            ["node", harness, str(CROP_JS)],
            input=json.dumps(vecs),
            capture_output=True, text=True, encoding="utf-8", check=True,
        )
    finally:
        Path(harness).unlink(missing_ok=True)

    js = json.loads(proc.stdout)
    assert len(js) == len(py) == len(vecs)

    mismatches = []
    for (sw, sh, aspect, x, zoom, y), pj, jj in zip(vecs, py, js):
        if pj != jj:
            mismatches.append(
                f"src={sw}x{sh} aspect={aspect} zoom={zoom} x={x} y={y}: "
                f"py={pj} js={jj}"
            )

    assert not mismatches, (
        f"{len(mismatches)}/{len(vecs)} crop vectors diverged between JS and Python:\n"
        + "\n".join(mismatches[:8])
    )
