# Hermes Agent Adaptation Notes

This skill was originally written for Claude Code. Below are the adaptation steps and lessons learned when porting it to Hermes Agent.

## Installation

```bash
git clone <repo> ~/.hermes/skills/<skill-name>
```

No `hermes skills install` or `skillhub` needed for standalone GitHub repos — direct clone works.

## Path Migration

All `~/.claude/skills/` references in SKILL.md must be changed to `~/.hermes/skills/`. Check both code blocks and inline text.

## Script Fixes Applied

### 1. Android Player Client (Critical)
yt-dlp's default web client needs a JS runtime and PO Token — both fail in most environments. Fix:

```
--extractor-args "youtube:player_client=android"
```

This avoids JS runtime requirement, PO Token 429s, and works without browser cookies.

### 2. VTT Parser (Critical)
yt-dlp produces `.vtt` by default, not `.srt`. The original script used `--convert-subs srt` which:
- Triggers an extra HTTP request (another 429 risk)
- Can fail silently if ffmpeg is missing

Fix: parse `.vtt` directly. VTT is nearly identical to SRT — same timestamp format, just uses `.` instead of `,` for milliseconds and has a `WEBVTT` header. A unified `parse_vtt_or_srt()` function handles both.

### 3. Exponential Backoff for 429
Three retries with `2^attempt` second delays (1s, 2s, 4s). Rate-limited retries only; network-unreachable errors skip immediately (no point retrying).

### 4. Language Fallback
`--fallback-lang en` (default). If `--lang zh` gets 429'd, auto-retry with English.

### 5. Network Pre-check Pitfall
The original `check_network()` used `curl https://www.youtube.com/` which hangs indefinitely on macOS without proxy configured. **Removed entirely** — yt-dlp handles its own connectivity.

## Debugging: Unbuffered Stderr

When running scripts via `terminal(background=true)`, Python's stderr buffering can cause complete silence even when the script is running fine. Use:

```bash
python3 -u script.py 2>&1
```

The `-u` flag forces unbuffered stdout/stderr — critical for monitoring long-running background processes.

## Testing Result

- **Subtitle extraction**: ✅ Works with Android client. 272 entries extracted from 18-min video, VTT parsed correctly.
- **Keyframe capture**: ⚠️ Requires YouTube video download access (blocked on some networks). Subtitles work via API even when video downloads don't. Error classification (NETWORK_UNREACHABLE vs RATE_LIMITED vs UNKNOWN) verified correct.
