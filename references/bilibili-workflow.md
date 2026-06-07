# Bilibili Workflow Reference

Session-tested details for processing Bilibili videos through the video-notes skill.

## Tool Compatibility Matrix

| Tool | Bilibili | YouTube | Notes |
|------|----------|---------|-------|
| **you-get** | ✅ (≤480p, cookieless) | N/A | Default: `dash-flv360-AVC`. Also downloads `.cmt.xml` danmaku |
| **yt-dlp** | ❌ (HTTP 412) | ✅ | Bilibili anti-bot. Requires cookies/auth |
| **Bilibili API** | ✅ (metadata only) | N/A | `api.bilibili.com/x/web-interface/view?bvid=` |
| **Whisper** | ✅ (transcription) | N/A | Fallback when no native subtitles |

## Whisper Model Selection

### Speed Reference

60s clip benchmarks are not representative of full videos — long audio has I/O overhead and thermal constraints. Full-video benchmarks are more reliable:

| Platform | Model | 60s clip | 9m44s full video | Real speed |
|----------|-------|:---:|:---:|:---:|
| M2 + MPS | small | 44s (0.7x) | 534s | ~0.9x |
| M2 + MPS | tiny | ~15s (0.25x) | 109s | ~0.19x |
| M2 CPU-only | small | ~300s (~5x) | — | avoid |
| M2 CPU-only | tiny | ~60s (~1x) | — | acceptable |

Conclusion: 60s clip benchmark overestimates small speed. On full videos, small degrades to ~0.9x (near realtime), tiny stays at ~0.19x (5x faster than realtime). Default to tiny for Chinese.

Check MPS: python3 -c "import torch; print(torch.backends.mps.is_available())"

### Accuracy

| Model | Size | English | Chinese |
|-------|------|---------|---------|
| `tiny` | 72MB (39M params) | ❌ garbled | ⚠️ usable, names/terms fuzzy |
| `small` | 461MB (244M params) | ✅ excellent | ✅ good, captures nuance |
| `medium` | 1.5GB (769M params) | ✅ best | ✅ best (untested on this machine) |

### Recommendation

| Scenario | Model |
|----------|-------|
| Chinese video (any length) | tiny (default) — 0.19x realtime, LLM only reads sampled outline |
| English video | small — tiny is garbled on English |
| Need exact quotes from video | small (sacrifice speed for word-level accuracy) |
| Intel Mac or MPS unavailable | tiny (small is ~5x realtime on CPU) |

All models cached at ~/.cache/whisper/ after first download.

## html_to_obsidian.py Quirk

The script auto-fetches the original video title via `yt-dlp --print title`. This works for YouTube but **fails for Bilibili** (HTTP 412). Always pass `--title` explicitly for Bilibili videos:

```bash
# ✅ Bilibili: use the title from Bilibili API (Step B1)
python3 scripts/html_to_obsidian.py /tmp/BVxxx-notes.html --title "视频标题"

# ❌ Don't rely on auto-fetch for Bilibili
python3 scripts/html_to_obsidian.py /tmp/BVxxx-notes.html  # yt-dlp will fail
```

## Session Test Results

Bilibili videos + benchmark processed:

| Video | Duration | Subtitles | Model | Time | Segments |
|-------|----------|-----------|-------|------|----------|
| 黄仁勋"聪明"定义 | 2:08 | None | small + English | ~3s | 37 |
| 段永平投资访谈 | 14:21 | None | tiny + Chinese | ~60s | 582 |
| Hermes 看板实战 | 20:17 | None | tiny + Chinese | ~90s | 644 |
| Whisper benchmark (M2+MPS) | 1:00 | — | small + Chinese | 44s | 19 |

Benchmark notes (2026-06-07): M2 MacBook Air 24GB, `torch.backends.mps.is_available()=True`, `--fp16 False`. Small model runs at 0.7x realtime with MPS — **faster than realtime**, not the 5x slowdown seen in CPU-only mode. The original "small is too slow" assumption (pitfall E19) was based on pure CPU without MPS acceleration.

| 付鹏对话高志凯 | 39:56 | None | tiny + Chinese | ~360s | 1940 | 对话视频，采样不足→用时间窗口聚合补充 |
| ERP巨头追捧的本体论 | 9:44 | None | tiny + Chinese | 109s | 275 |
| ERP巨头追捧的本体论 | 9:44 | None | small + Chinese | 534s | 280 |

All Bilibili videos had no native subtitles — Whisper fallback was always triggered.

## Dense Dialogue Supplement

When the sampled outline from `sample_subtitles.py` is too sparse for dialogue-heavy videos (very short segments), use time-range text aggregation as a supplement. See `references/dense-dialogue-supplement.md` for the full pattern.

2026-06-07 re-benchmark notes: small on a 9m44s full video took 534s (0.91x realtime) — the 60s clip benchmark at 0.7x was optimistic. tiny at 109s (0.19x) is 5x faster with comparable segment count (275 vs 280). For Chinese video notes where the LLM reads sampled outlines, tiny is clearly the right default.

## Parallel Transcription (Experimental)

`scripts/whisper_parallel.py` splits audio into overlapping chunks and processes them with multiple whisper workers. On M2 MPS, the gain is marginal (~30% faster) due to MPS contention, and segment-merge quality degrades. Not recommended as default — single-process tiny is fast enough. Use only for 30min+ videos where saving 1-2 minutes matters.

## Danmaku XML

`you-get` downloads a `.cmt.xml` alongside the video. Structure:
```xml
<i>
  <d p="time,mode,size,color,timestamp,pool,uid,hash">弹幕内容</d>
</i>
```

Can be parsed for audience reactions. Not yet integrated into the note generation pipeline.
