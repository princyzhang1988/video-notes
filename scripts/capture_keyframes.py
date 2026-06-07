#!/usr/bin/env python3
"""
Identify key subtitle moments and capture video frames at those timestamps.

Key fixes applied (from real-world testing):
  - Uses Android player client to avoid JS runtime / PO Token issues
  - Clear error messages distinguishing rate-limit vs network vs other failures
  - Retries with exponential backoff on transient errors
  - No network pre-check (yt-dlp handles its own connectivity)

Usage:
    python3 capture_keyframes.py <youtube_url> <subtitles.json> [--max-frames <n>] [--output-json <path>]

Output:
    JSON array of keyframe objects:
    [{"t": "mm:ss", "s": 123.4, "text": "...", "image_b64": "...", "score": 0.5}]
"""

import sys
import os
import re
import json
import base64
import subprocess
import tempfile
import time
import argparse


# ── Heuristics for identifying key moments ──────────────────────────────────

KEY_PHRASES = [
    r"\bintroducing\b", r"\bintroduce\b", r"\bpresent(ing)?\b", r"\bannounce\b",
    r"\blet('s| us) (look|talk|start|begin|dive)\b",
    r"\bfirst[,.]?\s", r"\bnext[,.]?\s", r"\bfinally[,.]?\s",
    r"\bstep \d+\b", r"\bphase \d+\b",
    r"\bin summary\b", r"\bthe key (insight|takeaway|point|finding)\b",
    r"\bmost important(ly)?\b", r"\bcrucially?\b", r"\bfundamentally\b",
    r"\bthe result is\b", r"\bwe found\b", r"\bwe discover(ed)?\b",
    r"\blet('s| us) (watch|see|look at|show)\b", r"\bhere (is|are|you (can )?see)\b",
    r"\bdemonstrat(e|ing|ion)\b", r"\bin action\b",
    r"\b\d+[kKmMbB%]?\s*(hours?|times?|years?|percent|x)\b",
    r"\b(zero|one|two|three|four|five|six|seven|eight|nine|ten)\s+\w+\b",
    r"\b(and )?now[,.]?\s*(let('s)?|we)\b", r"\bmoving on\b", r"\bso[,.]?\s+how\b",
    r"\bthe (first|second|third|fourth|final)\b",
    r"(首先|其次|最后|接下来|总结|关键|重要|核心|发现|展示|演示)",
]

KEY_PHRASE_PATTERNS = [re.compile(p, re.IGNORECASE) for p in KEY_PHRASES]

HIGH_VALUE_WORDS = {
    "introducing", "announcing", "revolutionary", "breakthrough", "first",
    "zero", "100%", "million", "billion", "key", "crucial", "fundamental",
    "result", "discover", "show", "demonstrate", "watch", "see",
}


def score_subtitle(entry: dict) -> float:
    text = entry["text"].lower()
    score = 0.0
    for pat in KEY_PHRASE_PATTERNS:
        if pat.search(text):
            score += 0.15
    words = set(re.findall(r"\b\w+\b", text))
    score += len(words & HIGH_VALUE_WORDS) * 0.1
    word_count = len(text.split())
    if word_count > 12:
        score += 0.1
    if word_count > 20:
        score += 0.1
    if text.rstrip().endswith((".", "。")):
        score += 0.05
    return min(score, 1.0)


def select_keyframes(entries: list[dict], max_frames: int = 8) -> list[dict]:
    if not entries:
        return []
    scored = [(score_subtitle(e), e) for e in entries]
    scored.sort(key=lambda x: x[0], reverse=True)
    selected, used_times = [], []
    for score, entry in scored:
        if len(selected) >= max_frames:
            break
        if score < 0.1:
            break
        t = entry["s"]
        if any(abs(t - u) < 60 for u in used_times):
            continue
        selected.append({**entry, "score": round(score, 3)})
        used_times.append(t)
    selected.sort(key=lambda x: x["s"])
    return selected


# ── Video download & frame extraction ───────────────────────────────────────

def ensure_yt_dlp():
    try:
        import yt_dlp  # noqa
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "yt-dlp", "-q", "--break-system-packages"],
            stderr=subprocess.DEVNULL,
        )


def classify_error(stderr_output: str) -> str:
    if "429" in stderr_output or "Too Many Requests" in stderr_output:
        return "RATE_LIMITED"
    if any(kw in stderr_output.lower() for kw in [
        "name or service not known", "connection refused",
        "network is unreachable", "could not resolve host",
        "connection timed out", "no route to host", "getaddrinfo",
        "errno 8", "errno 61", "errno 51", "errno 65",
    ]):
        return "NETWORK_UNREACHABLE"
    if "video unavailable" in stderr_output.lower():
        return "VIDEO_UNAVAILABLE"
    if "unable to download webpage" in stderr_output.lower():
        return "WEBPAGE_DOWNLOAD_FAILED"
    return "UNKNOWN"


def download_section(url: str, start_sec: float, duration: float, out_path: str,
                     max_retries: int = 2) -> tuple[bool, str]:
    start = max(0, start_sec - 1)
    end = start + duration + 2
    mm_start = f"{int(start)//60:02d}:{int(start)%60:02d}"
    mm_end   = f"{int(end)//60:02d}:{int(end)%60:02d}"
    section  = f"*{mm_start}-{mm_end}"

    last_error = ""
    for attempt in range(max_retries):
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--download-sections", section,
            "--format", "worst[ext=mp4]/worst",
            "--no-playlist",
            "--extractor-args", "youtube:player_client=android",
            "--quiet",
            "-o", out_path,
            url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        stderr_output = (result.stderr or "") + (result.stdout or "")

        if result.returncode == 0 and os.path.exists(out_path):
            return True, ""

        error_cat = classify_error(stderr_output)
        last_error = error_cat

        if error_cat == "RATE_LIMITED":
            wait = 2 ** attempt
            print(f"  ⚠ Rate limited, waiting {wait}s (attempt {attempt+1}/{max_retries})...",
                  file=sys.stderr)
            time.sleep(wait)
        elif error_cat == "NETWORK_UNREACHABLE":
            print(f"  ✗ Network unreachable — skipping (check firewall/VPN/proxy)", file=sys.stderr)
            return False, error_cat
        elif attempt < max_retries - 1:
            wait = 2 ** attempt
            print(f"  ⚠ Download failed ({error_cat}), retrying in {wait}s...", file=sys.stderr)
            time.sleep(wait)

    return False, last_error


def extract_frame(video_path: str, offset_sec: float, out_path: str) -> bool:
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(max(0, offset_sec)),
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "3",
        "-vf", "scale=960:-2",
        out_path,
    ]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0 and os.path.exists(out_path)


def image_to_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Capture keyframes from a YouTube video")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("subtitles", help="Path to subtitles JSON (from extract_subtitles.py)")
    parser.add_argument("--max-frames", "-n", type=int, default=8,
                        help="Max keyframes to capture (default: 8)")
    parser.add_argument("--output-json", help="Output JSON file path (default: stdout)")
    args = parser.parse_args()

    ensure_yt_dlp()

    with open(args.subtitles, encoding="utf-8") as f:
        entries = json.load(f)
    print(f"[keyframes] Loaded {len(entries)} subtitle entries", file=sys.stderr)

    keyframes = select_keyframes(entries, max_frames=args.max_frames)
    print(f"[keyframes] Selected {len(keyframes)} key moments:", file=sys.stderr)
    for kf in keyframes:
        print(f"  {kf['t']}  score={kf['score']}  \"{kf['text'][:60]}\"", file=sys.stderr)

    results = []
    error_counts = {}

    with tempfile.TemporaryDirectory() as tmpdir:
        for i, kf in enumerate(keyframes):
            sec = kf["s"]
            print(f"[keyframes] Capturing frame {i+1}/{len(keyframes)} at {kf['t']}...",
                  file=sys.stderr)

            video_path = os.path.join(tmpdir, f"clip_{i}.mp4")
            frame_path = os.path.join(tmpdir, f"frame_{i}.jpg")

            ok, error_cat = download_section(args.url, sec, duration=4, out_path=video_path)
            if not ok:
                if error_cat:
                    error_counts[error_cat] = error_counts.get(error_cat, 0) + 1
                print(f"  ✗ Failed ({error_cat})", file=sys.stderr)
                continue

            ok = extract_frame(video_path, offset_sec=1.5, out_path=frame_path)
            if not ok:
                print(f"  ✗ Failed to extract frame at {kf['t']}", file=sys.stderr)
                continue

            b64 = image_to_b64(frame_path)
            results.append({
                "t": kf["t"],
                "s": kf["s"],
                "text": kf["text"],
                "score": kf["score"],
                "image_b64": b64,
            })
            print(f"  ✓ Captured ({len(b64)//1024}KB)", file=sys.stderr)

    total_failures = sum(error_counts.values())
    print(f"[keyframes] Done: {len(results)}/{len(keyframes)} frames captured "
          f"({total_failures} failed)", file=sys.stderr)

    if total_failures > 0:
        for cat, count in sorted(error_counts.items()):
            if count > 0:
                print(f"  - {cat}: {count}", file=sys.stderr)

    output = json.dumps(results, ensure_ascii=False, indent=2)
    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"[keyframes] Saved to: {args.output_json}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
