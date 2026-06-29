"""Phase 2 self-checks: prompt build, JSON extraction, index mapping, dedup, chunking.

No network/claude calls — run_claude is the only impure part and is exercised in
the live smoke test, not here.
"""

from content_machine import select as s

SEGMENTS = [
    {"start": 0.0, "end": 5.0, "text": "Intro hook line.", "words": []},
    {"start": 5.0, "end": 20.0, "text": "Body of the first idea continues here.", "words": []},
    {"start": 20.0, "end": 26.0, "text": "Punchline of first idea.", "words": []},
    {"start": 26.0, "end": 30.0, "text": "Filler.", "words": []},
    {"start": 30.0, "end": 55.0, "text": "Second strong idea with a hook.", "words": []},
]


def test_prompt_contains_indices_timestamps_and_schema():
    p = s.build_selection_prompt(SEGMENTS, max_clips=3)
    assert "[0]" in p and "[4]" in p
    assert "00:30" in p                      # timestamp formatting
    assert "start_seg" in p and "score" in p  # schema instruction
    assert "ONLY a JSON object" in p


def test_extract_json_handles_chatty_output():
    assert s.extract_json_object('{"clips": []}') == {"clips": []}
    chatty = 'Sure! Here you go:\n{"clips": [{"start_seg": 0, "end_seg": 2}]}\nHope that helps.'
    assert s.extract_json_object(chatty)["clips"][0]["end_seg"] == 2


def test_clips_from_indices_maps_to_timestamps_and_clamps():
    raw = {"clips": [
        {"start_seg": 0, "end_seg": 2, "title": "First", "score": 9},
        {"start_seg": 99, "end_seg": 100, "title": "OOB", "score": 7},  # clamped to last
        {"start_seg": 4, "end_seg": 0, "title": "Reversed", "score": 6},  # swapped
    ]}
    clips = s.clips_from_indices(raw, SEGMENTS)
    assert clips[0].start == 0.0 and clips[0].end == 26.0     # seg0..seg2
    assert clips[1].start_seg == 4 and clips[1].end_seg == 4  # clamped
    assert clips[2].start_seg == 0 and clips[2].end_seg == 4  # reversed -> fixed


def test_dedup_prefers_higher_score_and_drops_overlaps_and_shorts():
    from content_machine.select import Clip
    clips = [
        Clip(start=0, end=26, start_seg=0, end_seg=2, score=9),   # keep (best)
        Clip(start=5, end=26, start_seg=1, end_seg=2, score=8),   # overlaps -> drop
        Clip(start=30, end=55, start_seg=4, end_seg=4, score=7),  # keep (disjoint)
        Clip(start=26, end=30, start_seg=3, end_seg=3, score=10), # too short -> drop
    ]
    chosen = s.dedup_and_filter(clips, max_clips=6)
    assert [c.start_seg for c in chosen] == [0, 4]               # timeline order, no overlap


def test_chunk_segments_splits_long_input():
    big = [{"text": "x" * 1000} for _ in range(30)]
    chunks = s.chunk_segments(big, char_budget=5000)
    assert len(chunks) > 1
    assert sum(len(c) for c in chunks) == 30                     # no segments lost
    assert chunks[0] == [0, 1, 2, 3, 4]                          # 5 * 1000 fits budget


def test_transcript_hash_stable_and_content_sensitive():
    t1 = {"segments": SEGMENTS}
    t2 = {"segments": SEGMENTS + [{"start": 55, "end": 60, "text": "more", "words": []}]}
    assert s.transcript_hash(t1) == s.transcript_hash({"segments": SEGMENTS})
    assert s.transcript_hash(t1) != s.transcript_hash(t2)
