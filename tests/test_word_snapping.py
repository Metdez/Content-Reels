"""Phase 33 — WORD-01: editor trim snaps to whisper's per-word boundaries.

transcript.json already carries `segments[].words[] = {word,start,end}`; the clip
editor payload's `boundaries` now includes those word edges (falling back to
segment start/end when a segment has no word timing).
"""

from __future__ import annotations

import json

from tests.conftest import seed_job


def test_editor_boundaries_include_word_timings(client):
    job_dir = seed_job(client.data_dir, "wordjob0001")
    data = client.get("/api/job/wordjob0001/clip/1").json()
    b = data["boundaries"]
    # seeded transcript: 8 segments x ~8 words -> far more snap points than the
    # ~18 you'd get from segment edges alone.
    assert len(b) > 40
    # a known word boundary from the seeded transcript is present
    tj = json.loads((job_dir / "transcript.json").read_text())
    w0 = tj["segments"][0]["words"][2]  # some interior word
    assert round(float(w0["start"]), 3) in b


def test_editor_boundaries_fall_back_to_segments_without_words(client):
    job_dir = seed_job(client.data_dir, "wordjob0002")
    # strip word timing from every segment
    tj = json.loads((job_dir / "transcript.json").read_text())
    n_segs = len(tj["segments"])
    for s in tj["segments"]:
        s.pop("words", None)
    (job_dir / "transcript.json").write_text(json.dumps(tj))

    data = client.get("/api/job/wordjob0002/clip/1").json()
    b = data["boundaries"]
    # only segment starts/ends (+0 and duration) — no word explosion
    assert len(b) <= 2 * n_segs + 2
    # still usable: segment-0 start is a boundary
    assert round(float(tj["segments"][0]["start"]), 3) in b
