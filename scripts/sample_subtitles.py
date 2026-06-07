#!/usr/bin/env python3
"""Sample subtitle JSON to create a structured outline for LLM consumption.

Instead of reading 600+ segments into context (~9K tokens), this produces
a ~2K token outline with time-sampled segments and high-info-density extracts.
"""

import json
import re
import sys
from pathlib import Path


def info_score(seg):
    """Score a segment by information density (heuristic)."""
    text = seg.get("text", "")
    score = 0
    # Longer segments likely have more content
    score += min(len(text) / 80, 3)  # cap at 3
    # Contains numbers (stats, dates, prices)
    if re.search(r'\d+', text):
        score += 1
    # Contains proper noun indicators (Chinese quotes, English words)
    if re.search(r'[A-Za-z]{3,}', text):
        score += 1
    # Contains key content markers
    if re.search(r'(关键|重要|核心|所以|因此|但是|然而|例如|比如)', text):
        score += 1
    return score


def sample_subtitles(subs, interval_minutes=3, top_n_per_window=3):
    """Sample subtitles: equal-interval + high-info picks."""
    if not subs:
        return []

    total_seconds = subs[-1]["s"] + 30  # rough estimate
    window = interval_minutes * 60

    sampled = []
    for start in range(0, int(total_seconds), window):
        end = start + window
        window_segs = [s for s in subs if start <= s["s"] < end]
        if not window_segs:
            continue

        # Pick: 1 time-anchor + top-N by info score
        anchor = window_segs[len(window_segs) // 2]  # middle
        scored = sorted(window_segs, key=info_score, reverse=True)
        picks = [anchor] + [s for s in scored[:top_n_per_window] if s != anchor]
        sampled.extend(picks[:top_n_per_window + 1])

    # Deduplicate by time, sort
    seen = set()
    result = []
    for s in sorted(sampled, key=lambda x: x["s"]):
        key = s["t"]
        if key not in seen:
            seen.add(key)
            result.append(s)
    return result


def minutes(seconds):
    return f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


def generate_outline(subs, output_path):
    """Generate a markdown outline from sampled subtitles."""
    sampled = sample_subtitles(subs)

    lines = []
    lines.append("# 视频字幕大纲")
    lines.append(f"总片段数: {len(subs)}, 采样: {len(sampled)}")
    lines.append(f"时长: {minutes(0)} - {minutes(subs[-1]['s'])}")
    lines.append("")

    # Group into time blocks
    blocks = {}
    for s in sampled:
        block_start = (int(s["s"]) // 180) * 180  # 3-min blocks
        key = f"{minutes(block_start)}-{minutes(block_start + 180)}"
        if key not in blocks:
            blocks[key] = []
        blocks[key].append(s)

    for time_range, segs in blocks.items():
        lines.append(f"## {time_range}")
        for seg in segs:
            text = seg["text"].strip()
            if len(text) > 200:
                text = text[:200] + "..."
            lines.append(f"- [{seg['t']}] {text}")
        lines.append("")

    # Topic shift detection (simple: big gaps between segments)
    lines.append("## 潜在话题边界")
    for i in range(1, len(sampled)):
        gap = sampled[i]["s"] - sampled[i - 1]["s"]
        if gap > 120:  # >2 min gap = likely topic shift
            lines.append(f"- {minutes(sampled[i-1]['s'])} → {minutes(sampled[i]['s'])} (间隔 {int(gap)}s)")

    outline = "\n".join(lines)

    with open(output_path, "w") as f:
        f.write(outline)

    print(f"Outline: {len(subs)} segments → {len(sampled)} sampled → {output_path}")
    print(f"  Estimated tokens: ~{len(outline) // 4}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <subs.json> [--output outline.md]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = "/tmp/outline.md"

    # Parse --output flag
    args = sys.argv[2:]
    for i, arg in enumerate(args):
        if arg == "--output" and i + 1 < len(args):
            output_file = args[i + 1]

    with open(input_file) as f:
        subs = json.load(f)

    generate_outline(subs, output_file)
