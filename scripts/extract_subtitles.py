#!/usr/bin/env python3
"""
Extract and clean subtitles from a YouTube video URL.
Outputs JSON with deduplicated subtitle entries, each with timestamp and text.

Key fixes applied (from real-world testing):
  - Uses Android player client to avoid JS runtime / PO Token / 429 issues
  - Parses WebVTT directly (no --convert-subs srt needed, avoids extra 429)
  - Exponential backoff retry on 429 errors
  - Falls back to English if requested language fails with 429

Usage:
    python3 extract_subtitles.py <youtube_url> [--output <path>] [--lang <lang>]

Output JSON format:
    [{"t": "mm:ss", "s": <seconds_float>, "text": "<content>"}, ...]
"""

import sys
import re
import json
import subprocess
import tempfile
import os
import time
import argparse
from collections import defaultdict


def ensure_yt_dlp():
    try:
        import yt_dlp  # noqa
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "yt-dlp", "-q", "--break-system-packages"],
            stderr=subprocess.DEVNULL
        )


def download_subtitles(url: str, lang: str = "en", max_retries: int = 3) -> str | None:
    """
    Download subtitles via yt-dlp using Android player client.
    Returns path to .vtt file content or None.
    Retries with exponential backoff on 429 errors.
    """
    last_error = None
    for attempt in range(max_retries):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_tmpl = os.path.join(tmpdir, "sub")
            cmd = [
                sys.executable, "-m", "yt_dlp",
                "--write-auto-subs",
                "--skip-download",
                "--sub-langs", lang,
                # Android client avoids JS runtime requirement and PO Token 429s
                "--extractor-args", "youtube:player_client=android",
                "-o", out_tmpl,
                "--quiet",
                url,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            stderr_output = (result.stderr or "") + (result.stdout or "")

            # Check for 429 rate limiting
            if "429" in stderr_output or "Too Many Requests" in stderr_output:
                wait = 2 ** attempt  # 1s, 2s, 4s
                print(f"[extract_subtitles] 429 rate limited (attempt {attempt+1}/{max_retries}), "
                      f"waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
                last_error = "429 Too Many Requests"
                continue

            if result.returncode != 0:
                last_error = stderr_output[-200:] if stderr_output else f"exit code {result.returncode}"
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    print(f"[extract_subtitles] yt-dlp failed (attempt {attempt+1}/{max_retries}): "
                          f"{last_error[:80]}, retrying in {wait}s...", file=sys.stderr)
                    time.sleep(wait)
                continue

            # Find produced .vtt file (we no longer convert to srt)
            for f in os.listdir(tmpdir):
                if f.endswith(".vtt"):
                    path = os.path.join(tmpdir, f)
                    with open(path, encoding="utf-8") as fh:
                        return fh.read()

            # Fallback: maybe yt-dlp produced .srt anyway (old behavior)
            for f in os.listdir(tmpdir):
                if f.endswith(".srt"):
                    path = os.path.join(tmpdir, f)
                    with open(path, encoding="utf-8") as fh:
                        return fh.read()

            # No subtitle file found
            last_error = "No subtitle file produced (no .vtt or .srt found)"
            continue

    if last_error:
        print(f"[extract_subtitles] All {max_retries} attempts failed. Last error: {last_error}", file=sys.stderr)
    return None


def parse_vtt_or_srt(content: str) -> list[dict]:
    """Parse WebVTT or SRT content into list of {s, t, text} dicts, deduplicated."""
    # Check if it's VTT (has WEBVTT header)
    is_vtt = content.strip().startswith("WEBVTT")

    # Remove WEBVTT header and any style blocks
    if is_vtt:
        # Remove header line(s)
        content = re.sub(r'^WEBVTT.*?\n', '', content, flags=re.MULTILINE)
        # Remove NOTE blocks
        content = re.sub(r'^NOTE\s+.*?(?=\n\n|\Z)', '', content, flags=re.MULTILINE | re.DOTALL)
        # Remove style blocks (::cue etc.)
        content = re.sub(r'^::.*?(?=\n\n|\Z)', '', content, flags=re.MULTILINE | re.DOTALL)

    # Split into blocks (separated by blank lines)
    blocks = re.split(r"\n\n+", content.strip())
    entries = []

    for block in blocks:
        lines = block.strip().split("\n")
        # Find timestamp line: matches HH:MM:SS.mmm or HH:MM:SS,mmm
        ts_line = next((l for l in lines if re.match(r"\d{2}:\d{2}:\d{2}[.,]\d{3}", l)), None)
        if not ts_line:
            # Also try simpler pattern
            ts_line = next((l for l in lines if re.search(r"\d{2}:\d{2}:\d{2}", l)), None)
        if not ts_line:
            continue

        # Extract start timestamp
        start_match = re.match(r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})", ts_line)
        if not start_match:
            continue

        h, m, s, ms = start_match.groups()
        sec = int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

        # Collect text lines after timestamp
        ts_idx = lines.index(ts_line)
        text_lines = []
        for l in lines[ts_idx + 1:]:
            l = l.strip()
            if not l:
                continue
            # Remove HTML-like tags (common in VTT)
            l = re.sub(r"<[^>]+>", "", l)
            if l:
                text_lines.append(l)

        text = " ".join(text_lines).strip()
        if text and len(text) >= 3:
            entries.append((sec, text))

    if not entries:
        return []

    # Group into ~4s buckets, keep longest text per bucket
    chunks = defaultdict(list)
    for sec, text in entries:
        chunks[int(sec / 4)].append((sec, text))

    result = []
    last_text = ""
    for key in sorted(chunks):
        sec, text = max(chunks[key], key=lambda x: len(x[1]))
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r">>\s*\[.*?\]\s*>>", "", text).strip()
        if len(text) < 5 or text == last_text:
            continue
        total = int(sec)
        ts_fmt = f"{total // 60:02d}:{total % 60:02d}"
        result.append({"t": ts_fmt, "s": round(sec, 1), "text": text})
        last_text = text

    # Final pass: remove near-duplicates
    seen, final = set(), []
    for e in result:
        key = e["text"][:50]
        if key in seen:
            continue
        seen.add(key)
        final.append(e)

    return final


def main():
    parser = argparse.ArgumentParser(description="Extract YouTube subtitles to JSON")
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--output", "-o", help="Output JSON file path (default: stdout)")
    parser.add_argument("--lang", default="en", help="Subtitle language code (default: en)")
    parser.add_argument("--fallback-lang", default="en",
                        help="Fallback language if primary fails with 429 (default: en)")
    args = parser.parse_args()

    ensure_yt_dlp()

    # Try primary language first
    print(f"[extract_subtitles] Downloading {args.lang} subtitles for: {args.url}", file=sys.stderr)
    subtitle_content = download_subtitles(args.url, args.lang)

    # Fallback to English if primary language failed
    if not subtitle_content and args.lang != args.fallback_lang:
        print(f"[extract_subtitles] Primary language '{args.lang}' failed, "
              f"falling back to '{args.fallback_lang}'...", file=sys.stderr)
        subtitle_content = download_subtitles(args.url, args.fallback_lang)

    if not subtitle_content:
        print("[extract_subtitles] ERROR: No subtitles found. "
              "Video may not have auto-generated captions, or YouTube is rate-limiting.",
              file=sys.stderr)
        sys.exit(1)

    # Detect format and parse
    fmt = "VTT" if subtitle_content.strip().startswith("WEBVTT") else "SRT"
    print(f"[extract_subtitles] Detected {fmt} format, parsing...", file=sys.stderr)
    entries = parse_vtt_or_srt(subtitle_content)
    print(f"[extract_subtitles] Extracted {len(entries)} entries (deduplicated)", file=sys.stderr)

    output = json.dumps(entries, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"[extract_subtitles] Saved to: {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
