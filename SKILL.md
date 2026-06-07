---
name: video-notes
slug: video-notes
version: 1.6.0
author: princyzhang
description: 把 YouTube / Bilibili 视频 / 小宇宙播客变成精美的结构化笔记。自动提取字幕（或 Whisper 转录）、生成核心论点总结和 SVG 图表，输出 HTML + Obsidian Markdown。适用于技术演讲、公开课、播客、产品发布会等场景。This skill should be used when a user provides a YouTube, Bilibili or Xiaoyuzhou FM URL and asks to take notes, summarize a video, or create a study document from video content.
---

> **Forked from [kaimomo99/video-notes](https://clawhub.ai/kaimomo99/video-notes)**
> 感谢原作者 [kaimomo99](https://clawhub.ai/kaimomo99) 的优秀工作！本版本在其基础上增加了 Bilibili Whisper 转录回退、小宇宙 FM 播客支持、采样大纲、字幕注入等增强功能。
>
> 原版（YouTube + Bilibili 基础支持）：https://clawhub.ai/kaimomo99/video-notes

# Video Notes Skill

Convert YouTube or Bilibili videos into a polished, self-contained HTML notes document with:
- **Executive summary** (~300 words) capturing the core arguments
- AI-generated structured notes with SVG diagrams
- **Keyframe gallery** — screenshots auto-captured at key moments, each linking back to the source
- Fixed sidebar navigation with scroll-spy
- Searchable raw subtitle panel (click any line → jump to that timestamp)

**Supported platforms:**
- **YouTube** — native subtitle extraction via yt-dlp (Android client, VTT parser)
- **Bilibili** — API metadata + B站直链下载 + Whisper transcription fallback
- **小宇宙 FM** — browser-based show notes extraction (no audio download needed); structured HTML + MD from rich timeline and concept annotations

## YouTube Workflow

### Step 1: Extract Subtitles

```bash
python3 scripts/extract_subtitles.py <youtube_url> --output /tmp/subs.json
```

- Default language: `en`. Pass `--lang zh` or `--lang zh-Hans` for Chinese.
- The script uses Android player client (avoids JS runtime + PO Token issues), parses WebVTT natively, and has built-in exponential backoff retry on 429 errors.
- If the primary language fails with 429, it auto-falls back to English. Override with `--fallback-lang`.
- **YouTube 在中国大陆被墙**：需设置代理环境变量 `export https_proxy=http://127.0.0.1:7897 http_proxy=http://127.0.0.1:7897`。
- If the video has no auto-generated captions, inform the user and stop.

Output: `[{"t": "mm:ss", "s": 123.4, "text": "..."}]`

### Step 2: Capture Keyframes (requires ffmpeg) — ⚠️ SKIP BY DEFAULT

**默认不抓取关键帧。** 原因：关键帧 base64 嵌入 HTML 会消耗大量 token，且大多数笔记场景不需要截图。只有当用户明确说「截图」「关键帧」「画面」时，才执行此步骤。

需要时运行：

```bash
python3 scripts/capture_keyframes.py \
  <youtube_url> /tmp/subs.json \
  --max-frames 8 \
  --output-json /tmp/keyframes.json
```

Output: `[{"t": "mm:ss", "s": 123.4, "text": "...", "score": 0.5, "image_b64": "..."}]`

- Default `--max-frames` is 8; reduce for faster generation or increase for longer videos.
- Network-unreachable errors are surfaced immediately instead of being silently skipped.
- Rate-limited downloads get exponential backoff retry.
- **跳过时**：`{{KEYFRAMES_JSON}}` 设为 `[]`，HTML 中 keyframe gallery 区域会自动隐藏。

### Step 3: Understand Content via Sampled Outline (NOT full subtitles)

⚠️ **不要读取全量字幕 JSON。** 用采样脚本生成结构化大纲，只读大纲进上下文：

```bash
python3 scripts/sample_subtitles.py /tmp/subs.json --output /tmp/outline.md
```

脚本逻辑：
- 按时间等距采样（每 ~3 分钟取一条）
- 按信息密度提取关键段落（长度异常/含数字/含专有名词的段落加权）
- 输出结构：`## 00:00-03:00 主题推断` + 代表性文本片段

然后 **只读取大纲文件**（~2K token），据此理解：
- 视频的主要话题和整体结构
- 关键概念、论据、术语
- 自然的话题边界（主题切换点）

不需要也不应该读全量字幕 JSON。

### Step 4: Generate HTML Notes

Use `assets/note-template.html` as the foundation. Fill in each placeholder:

| Placeholder | Content |
|---|---|
| `{{TITLE}}` | Page `<title>` tag |
| `{{SIDEBAR_NAV}}` | `.sb-logo` block + `.nav-a` links for each section |
| `{{SUMMARY}}` | Executive summary HTML (see below) |
| `{{MAIN_CONTENT}}` | Hero block + all note sections |
| `{{SUBTITLE_SEC_NUM}}` | Section number for the subtitle panel (e.g. `6`) |
| `{{VIDEO_URL}}` | Full YouTube URL |
| `{{VIDEO_ID}}` | YouTube video ID (e.g. `dQw4w9WgXcQ`) |
| `{{SUBTITLE_JSON}}` | 占位符 `__SUBS_JSON__`（不带引号）— 生成后用 `inject_subs.py` 注入为 JS 数组字面量 |
| `{{KEYFRAMES_JSON}}` | `[]` (skip by default; only fill when user asks for screenshots) |
| `{{SECTION_IDS}}` | JS array: `['hero','summary','s1','s2','keyframes','subtitles']` |

**⚠️ 生成 HTML 后必须运行注入脚本**，将字幕 JSON 嵌入 HTML：

```bash
python3 scripts/inject_subs.py /tmp/<video-id>-notes.html /tmp/subs.json
```

这样字幕 JSON 不出现在 LLM 上下文（省 token），但最终 HTML 可离线使用。

#### Executive Summary (`{{SUMMARY}}`)

Write ~300 words of HTML paragraphs inside `<p>` tags. Structure:
1. **One-sentence core thesis** — what is the speaker's central claim?
2. **Main argument 1** — first major thread (2–3 sentences)
3. **Main argument 2** — second major thread
4. **Main argument 3** — third major thread (if applicable)
5. **Closing** — key prediction, implication, or call to action

Use `<strong style="color:var(--text)">` for emphasis. Keep line-height loose (`line-height:2`).

#### Hero Section

Always include a hero section (`id="hero"`) with:
- `.hero-badge`: speaker name + event/source
- `<h1>`: video title (concise, impactful)
- `.hero-sub`: speaker · role · note type
- `.chips`: 3–5 topic tags
- `.hero-quote`: the single most memorable quote

#### Note Sections

For each major topic area, create `<div class="sec" id="sN">` with:
- `.sec-hd` header (numbered `.sec-n` + `.sec-title`)
- Content using: `.card`, `.g2`/`.g3` grids, `.diag` SVG diagrams, `.tl` timelines, `.ql` quotes

#### SVG Diagrams (`.diag` blocks)

Generate SVGs for comparisons, progressions, and architectures:

```
Background: rgba(R,G,B,.4) fill + rgba(R,G,B,.3) stroke
Labels: fill="#fff" font-weight="700"; sublabels: fill="#aaa" font-size="9-10"
Arrows: › in <text>, colored to match the row
Connectors: stroke="rgba(255,255,255,.12)" stroke-dasharray="3,3"
```

Color palette:
- Blue flow: `#5b8dee` → `#9b7cf4` | Green flow: `#3ecf8e` → `#5b8dee`
- Old/danger: `rgba(244,63,94,.4)` | Mid: `rgba(240,169,70,.4)` | New: `rgba(62,207,142,.4)`

#### Sidebar Navigation

```html
<div class="sb-logo">
  <div class="sb-logo-icon">🎬</div>
  <h2>{{Short Title}}</h2>
  <p>{{Speaker}} · {{Source}}</p>
</div>
<a class="nav-a active" href="#hero"><span class="nav-icon">🏠</span>概览</a>
<a class="nav-a" href="#summary"><span class="nav-icon">✦</span>核心总结</a>
<!-- one .nav-a per note section -->
<div class="nav-sep"></div>
<!-- Only include keyframes nav if keyframes were captured → `{{KEYFRAMES_JSON}}` is non-empty -->
<a class="nav-a" href="#subtitles"><span class="nav-icon">📄</span>原始字幕</a>
```

### Step 5: Inject Subtitles + Save

**⚠️ 生成 HTML 后立即注入字幕**（不在 LLM 上下文中操作，省 token）：

```bash
python3 scripts/inject_subs.py /tmp/<video-id>-notes.html /tmp/subs.json
```

将 HTML 保存到你的 Obsidian vault 或笔记目录（路径根据你的环境调整）：

```bash
cp /tmp/<video-id>-notes.html "<your-vault>/资源/<sanitized-title>.html"
open /tmp/<video-id>-notes.html
```

- **Sanitized title**: Remove special chars, keep it short and readable
- Tell the user: save path, subtitle entry count, keyframe count, sections covered.

### Step 6: Convert to Obsidian Markdown

After the HTML is generated, convert it to an Obsidian-flavored Markdown note:

```bash
python3 scripts/html_to_obsidian.py /tmp/<video-id>-notes.html
```

The script:
- **Auto-fetches the original YouTube video title** via yt-dlp and uses it as H1
- The hero title (e.g. "Run, Don't Walk") becomes a **subtitle blockquote** below H1
- Adds YAML frontmatter with tags, video URL, creation date, and `original-title`
- Converts HTML to clean Markdown (using html2text)
- SVG diagrams are flattened to text descriptions
- Pass `--title "Custom Title"` to override, or `--output <path>` for custom path
- Pass `--vault <vault-path>` and `--subfolder <folder>` to customize save location

Dependencies: `html2text`, `beautifulsoup4`, `yt-dlp` (auto-installed if missing).

## Bilibili Workflow

Bilibili videos may or may not have native subtitles. The workflow branches at Step B1:

```
B1: Get video metadata → check subtitles
  ├── ✅ Has subtitles → B2a: Download subtitle JSON → skip to B5
  └── ❌ No subtitles → B2b: Download video → B3: Extract audio → B4: Whisper → B5
B5-B7: Same as YouTube Steps 4-6
```

### Step B1: Get Video Metadata & Check Subtitles

If the user provides a `b23.tv` short link, resolve it first. If the short link or direct Bilibili access fails with Connection reset (common from some networks), **immediately ask the user for the BV ID** — don't waste turns trying different URLs. The BV ID is the `BVxxxxxxxxx` string visible in every Bilibili share link.

Once you have the BV ID, use the Bilibili web API:

```python
import requests
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://www.bilibili.com/',
}
BV = '<video_bv_id>'
r = requests.get(f'https://api.bilibili.com/x/web-interface/view?bvid={BV}', headers=headers)
data = r.json()
# data['data']['title'], data['data']['duration'], data['data']['cid']
# data['data']['subtitle']['list'] — if non-empty: HAS subtitles → go to B2a
#                                       if empty:     NO subtitles → go to B2b
```

**Decision at this point:**

- If `subtitle['list']` is non-empty → go to **Step B2a** (download subtitles directly, skip video download)
- If `subtitle['list']` is empty → go to **Step B2b** (download video + Whisper transcription)

---

### Path A: Native Subtitles Available

#### Step B2a: Download Subtitle JSON Directly

Bilibili stores subtitles as JSON at the URLs returned in `subtitle['list']`:

```python
for sub in data['data']['subtitle']['list']:
    url = sub['subtitle_url']
    if url.startswith('//'): url = 'https:' + url
    r = requests.get(url, headers=headers)
    subtitle_data = r.json()
    # subtitle_data['body'] contains the subtitle entries with 'from', 'to', 'content'
    # Convert to standard format and save as /tmp/subs.json
```

Then skip to **Step B5** (generate HTML notes).

---

### Path B: No Native Subtitles (Whisper Fallback)

#### Step B2b: Download Video

**优先使用 B 站 API 直链**（2026年6月实测 you-get/yt-dlp 均返回 HTTP 412）：

详见 `references/bilibili-api-download.md`。核心流程：`api.bilibili.com/x/player/playurl` → 获取 `durl[0].url` → 带 Referer 下载。

备选方案（部分环境可用）：
```bash
python3 -m you_get --format=dash-flv360-AVC -o /tmp <bilibili_url>
```

### Step B3: Extract Audio and Transcribe with Whisper

Most Bilibili videos lack subtitles. Extract audio and transcribe with Whisper:

```bash
# Install Whisper if not already available
pip install openai-whisper

# Extract audio (16kHz mono WAV)
ffmpeg -y -i /tmp/<downloaded>.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 /tmp/bilibili_audio.wav

# Transcribe with Whisper
# 中文默认 tiny (M2 MPS ~0.15x 实时，10分钟视频约1.5分钟)
# 英文用 small（tiny 英文不可用）
# Model selection: see references/bilibili-workflow.md for full details
python3 -m whisper /tmp/bilibili_audio.wav \
  --model tiny \
  --language Chinese \
  --output_dir /tmp \
  --output_format json \
  --fp16 False
```

- Use `--language Chinese` for Mandarin videos, `English` for English.
- **⚠️ Chinese output may be Traditional (繁体)**: Whisper's `Chinese` language code does not distinguish Simplified vs Traditional, and smaller models (tiny/small) often default to Traditional. Always run Step B4's `zhconv` conversion to ensure Simplified Chinese (简体) output.
- **Model selection:**
  - **`tiny` (72MB，中文默认)**: M2 MPS 下 ~0.15x 实时速度（10 分钟视频约 1.5 分钟）。中文内容理解足够，LLM 只看采样大纲不读全文，少量识别错误不影响笔记质量。
  - **`small` (461MB)**: ~0.7-1.0x 实时速度。用于英文视频（tiny 英文不可用）或对精度要求极高的中文场景。
  - **MPS check**: `python3 -c "import torch; print(torch.backends.mps.is_available())"` — MPS 可用时 tiny 极快。
  - 所有模型缓存在 `~/.cache/whisper/`，首次下载后复用。
- Output: `/tmp/bilibili_audio.json` with segments containing `start`, `end`, `text`.

### Step B4: Convert Whisper Output to Subtitle JSON (with 繁→简 conversion)

Convert Whisper's segment format to the standard video-notes subtitle format. **For Chinese (`--language Chinese`), always run `zhconv` to convert Traditional to Simplified:**

```python
import json
from zhconv import convert

with open('/tmp/bilibili_audio.json') as f:
    whisper_data = json.load(f)

subs = []
for seg in whisper_data['segments']:
    text = seg['text'].strip()
    # 繁体→简体（中文视频必做，英文视频跳过）
    text = convert(text, 'zh-cn')
    subs.append({
        "t": f"{int(seg['start'])//60:02d}:{int(seg['start'])%60:02d}",
        "s": round(seg['start'], 1),
        "text": text
    })

with open('/tmp/subs.json', 'w') as f:
    json.dump(subs, f, ensure_ascii=False, indent=2)
```

- `zhconv` dependency: `pip install zhconv` (pure Python, ~200KB, no C extensions)
- For English videos, skip the `convert()` call

Output format: `[{"t": "mm:ss", "s": 123.4, "text": "..."}]` — compatible with Steps B5-B7 below.

### Steps B5–B7: Same as YouTube Steps 4–6

After obtaining the subtitle JSON, proceed with the standard workflow:
- **Step B5** → YouTube Step 4: Generate HTML Notes
- **Step B6** → YouTube Step 5: Save HTML
- **Step B7** → YouTube Step 6: Convert to Obsidian Markdown

Use `{{VIDEO_URL}}` = the Bilibili URL and `{{VIDEO_ID}}` = the BV ID. Skip keyframes (set `{{KEYFRAMES_JSON}}` to `[]`) unless the video download is accessible.

⚠️ **Bilibili template adaptation**: The `assets/note-template.html` has YouTube URLs hardcoded in its JavaScript (subtitle click-to-jump links and keyframe gallery links). After filling in placeholders, replace the YouTube link patterns with Bilibili equivalents:

```python
html = html.replace(
    "const u=`https://www.youtube.com/watch?v=${vid}&t=${Math.floor(s.s)}s`;",
    "const u=`https://www.bilibili.com/video/${vid}?t=${Math.floor(s.s)}`;"
)
html = html.replace(
    "const u=`https://www.youtube.com/watch?v=${vid}&t=${Math.floor(k.s)}s`;",
    "const u=`https://www.bilibili.com/video/${vid}?t=${Math.floor(k.s)}`;"
)
```

### Bilibili-Specific Notes

- **Danmaku XML**: `you-get` downloads a `.cmt.xml` file alongside the video. Parse it for audience reactions and trending comments — use as supplementary content in the notes.
- **Cookieless access**: `you-get` works for ≤480p without Bilibili login. For HD, pass `--cookies cookies.txt` (export from browser).
- **B 站 API 直链下载**：you-get/yt-dlp 均可能返回 HTTP 412，此时用 `references/bilibili-api-download.md` 的 API 方法。
- **Whisper model selection**: See `references/bilibili-workflow.md` for the full model-size-vs-language-vs-duration tradeoff table.
- **长视频转录后的处理**：Whisper 转录 30+ 分钟视频会产生 1000+ 片段。不要逐段读取，用 Python 按时间间隔采样（每 ~3 分钟取一条），快速建立内容结构，再据此生成笔记。
- **`html_to_obsidian.py` 对 B 站视频**：必须传 `--title`（yt-dlp 对 B 站返回 HTTP 412）。

## Xiaoyuzhou FM (小宇宙) Workflow

小宇宙播客不同于 YouTube/Bilibili——它没有视频流也没有自动字幕，但 **show notes（节目笔记）质量极高**，通常包含详细时间轴和概念注释。不需要下载音频或 Whisper 转录——直接从 show notes 提取结构化内容。

### Step X1: Extract Show Notes via Browser

使用浏览器打开播客页面，提取 `article` 元素的完整文本。

这一步获取的内容包含：
- 节目介绍和开场白
- 完整时间轴（`03:22 标题 —— 描述` 格式）
- 概念注释（`📑 猜你想看` 段落：时间戳 + 概念名 + 释义）
- 嘉宾介绍、引用、往期推荐
- 评论区热门留言

**关键信息提取：**
- 节目标题、主持、嘉宾、时长、播放量、评论数 — 从页面获取
- 时间轴条目 — 解析 `HH:MM:SS 标题` 格式
- 概念词典 — 解析 `📑 猜你想看` 段落中 `时间戳 概念名：释义` 格式
- 精选评论 — 选取高赞评论

### Step X2: Understand and Structure the Content

阅读 show notes 内容，理解：
- 节目的核心论点和整体结构
- 嘉宾的关键洞察和反直觉观点
- 引用的历史事件、书籍、概念
- 自然的话题转折点

### Step X3: Generate HTML Notes

**不要使用 `assets/note-template.html`（那是为视频/字幕设计的）。** 为播客定制 HTML，包含以下特性：

| 特性 | 说明 |
|------|------|
| 深色主题 | 与视频笔记风格统一 |
| 侧边导航 | scroll-spy，多章节跳转 |
| Hero 区 | 节目标题、主持/嘉宾、播放统计、标签、金句引用 |
| 核心论点总结 | ~300 词 HTML 段落 |
| 按主题分章节 | 4-7 个章节，包含 SVG 图表 |
| 完整时间轴 | 时间戳 + 标题 + 描述 |
| 概念词典 | 网格布局，时间戳 + 术语 + 释义 |
| 精选评论 | 引用格式展示高赞评论 |
| 无字幕面板 | 播客没有字幕，不需要此区域 |
| 无关键帧 | 播客没有视频，不需要此区域 |

**CSS 变量与视频笔记模板保持一致**（`--bg: #1a1a2e` 等）。

### Step X4: Generate Obsidian Markdown

**不要用 `html_to_obsidian.py`**（它依赖 yt-dlp 获取 YouTube 标题，小宇宙播客会失败）。直接手写 Markdown 文件：

```markdown
---
tags: [播客, AI, ...]
podcast: 知行小酒馆
episode: E237
guest: Cage
host: 雨白
duration: 87分钟
date: YYYY-MM-DD
url: https://www.xiaoyuzhoufm.com/episode/...
---

# 节目标题

> 播客名 · 集数 · 主持 × 嘉宾 · 时长

## 核心论点

...（与 HTML 中的总结对应）

## 一、章节标题

...（Markdown 格式的正文，表格用管道符，引用用 >）

## 📚 概念词典

| 时间戳 | 概念 | 释义 |
|--------|------|------|

## 🕐 完整时间轴

- **HH:MM** — 标题。描述

## 💬 精选评论

> "评论内容" — 作者（👍N）
```

### Step X5: Save

播客笔记保存到你的 Obsidian vault 或笔记目录。

### Xiaoyuzhou-Specific Notes

- **不需要网络代理**：小宇宙页面可直接访问。
- **不需要 yt-dlp / you-get / Whisper / ffmpeg**：完全基于浏览器 DOM 提取 + LLM 处理。
- **show notes 质量决定笔记质量**：小宇宙的 show notes 通常比 B 站更详细（含概念注释），直接利用即可。
- **评论区是宝库**：小宇宙用户评论质量通常很高，选取 5-8 条高赞评论加入笔记。
- **模板独立**：不要复用 `note-template.html` 的字幕/关键帧 JS 逻辑，播客页面结构完全不同。

## Non-小宇宙 Podcast Workflow (Relay FM, etc.)

小宇宙工作流的核心思想（浏览器提取 show notes → 定制 HTML → 手写 MD）同样适用于其他播客平台。但需要注意以下差异：

### Cloudflare 保护

Relay FM 等国际播客网站通常有 Cloudflare 反爬保护，浏览器和 curl 都会失败。可使用 Bright Data 等代理服务。

### Show Notes 稀薄时的补救

部分播客（如 Cortex）的 show notes 只有链接列表，没有小宇宙那种详细时间轴和概念注释。此时需要：

1. **从 show notes 提取链接列表**，识别核心话题和嘉宾的关键文章
2. **批量抓取链接文章**（通常 5-8 篇即可覆盖全部话题）
3. **以文章内容为骨架生成笔记**，而不是凭空推测播客对话内容
4. 在笔记末尾注明数据来源（"基于 show notes 及 N 篇相关文章综合整理"）

## Quality Guidelines

- **Summary is mandatory** — always write the executive summary; it's the first thing readers see.
- **Keyframes are optional** — skip by default unless the user explicitly asks for screenshots.
- **Depth over breadth** — 4–7 well-developed sections beat 12 shallow ones.
- **Diagrams are mandatory** when content has comparisons, progressions, or architectures.
- **Language matching** — write in the same language as the user's request, regardless of the video's language.

## Pitfalls & Known Issues

### YouTube

| # | Pitfall | Fix |
|---|---------|-----|
| 1 | yt-dlp requires JS runtime → "video not available" | Use `--extractor-args youtube:player_client=android` |
| 2 | Web client requires PO Token → 429 errors | Android player client bypasses PO Token entirely |
| 3 | Chinese (zh-Hans) persistent 429 | Auto-fallback to English; use `--fallback-lang` to override |
| 4 | yt-dlp produces VTT not SRT → parse failure | `parse_vtt_or_srt()` handles both formats |
| 5 | Keyframe download silently skipped on network error | Network pre-check + clear error categorization |

### Bilibili

| # | Pitfall | Fix |
|---|---------|-----|
| 6 | you-get / yt-dlp return HTTP 412 | Use Bilibili API playurl (see `references/bilibili-api-download.md`) |
| 7 | Whisper Chinese output is Traditional (繁体) | Always run `zhconv.convert(text, 'zh-cn')` in Step B4 |
| 8 | `html_to_obsidian.py` auto-fetch fails for Bilibili | Always pass `--title` explicitly |
| 9 | `note-template.html` hardcodes YouTube URLs | Replace YouTube link patterns with Bilibili equivalents |
| 10 | Bilibili API intermittent Connection reset | Ask user for BV ID directly, don't hammer the API |

### General

| # | Pitfall | Fix |
|---|---------|-----|
| 11 | Reading full subtitle JSON floods context | Use `sample_subtitles.py` for ~2K token outline |
| 12 | 小宇宙播客 `html_to_obsidian.py` fails (yt-dlp dependency) | Hand-write Markdown directly |
| 13 | Whisper transcription of 30+ min videos creates 1000+ segments | Sample by time intervals, don't read all segments |
| 14 | Dense dialogue videos have sparse samples | Supplement with time-range text aggregation (see `references/dense-dialogue-supplement.md`) |
