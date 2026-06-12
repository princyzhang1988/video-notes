---
name: video-notes
slug: video-notes
version: 2.1.0
author: 2992638402-art
description: 把 YouTube / Bilibili / 小宇宙播客 / 小红书帖子 / 微信公众号文章变成精美的结构化笔记。自动提取内容（字幕 / Whisper 转录 / show notes / __INITIAL_STATE__ JSON）、生成核心论点总结和 SVG 图表，输出 HTML + Obsidian Markdown。统一存入知识库/30.Resources/。当用户提供 YouTube、Bilibili、小宇宙 FM、小红书或微信公众号链接需要记笔记时使用。
---

# Video Notes Skill

Convert YouTube / Bilibili / Xiaoyuzhou FM / Xiaohongshu content into polished, self-contained HTML + Obsidian Markdown notes with:
- **Executive summary** (~300 words) for video/podcast content, **Thiel-style insight** for XHS posts
- AI-generated structured notes with SVG diagrams (video/podcast) or numbered methodology steps (XHS)
- **Keyframe gallery** — screenshots auto-captured at key moments (video only, skip by default)
- Fixed sidebar navigation with scroll-spy (video/podcast) or centered single-page layout (XHS)
- Searchable raw subtitle / transcript panel

**Supported platforms:**
- **YouTube** — native subtitle extraction via yt-dlp (Android client, VTT parser)
- **Bilibili** — API metadata + B站直链下载（you-get/yt-dlp 均已失效，用 playurl API 兜底） + Whisper transcription fallback
- **小宇宙 FM** — browser-based show notes extraction (no audio download needed); structured HTML + MD from rich timeline and concept annotations
- **小红书** — `__INITIAL_STATE__` JSON 解析（需 cookies 认证），支持 xhslink.com 短链自动 302 跟踪；图文 / 视频帖子均支持

## URL 路由（优先判断渠道）

收到链接后，第一步判断平台，走对应分支：

| 链接特征 | 平台 | 走哪条分支 |
|---------|------|-----------|
| `youtube.com/watch` 或 `youtu.be` | YouTube | → YouTube Workflow |
| `bilibili.com/video` 或 `b23.tv` | Bilibili | → Bilibili Workflow |
| `xiaoyuzhoufm.com` | 小宇宙 FM | → Xiaoyuzhou FM Workflow |
| `xiaohongshu.com` 或 `xhslink.com` | 小红书 | → Xiaohongshu Workflow |
| `mp.weixin.qq.com` | 微信公众号 | → WeChat Article Workflow |

**所有平台最终产物一致：HTML + Obsidian Markdown，存入 `知识库/30.Resources/视频/`。**

## YouTube Workflow

### Step 1: Extract Subtitles

```bash
python3 ~/.hermes/skills/video-notes/scripts/extract_subtitles.py <youtube_url> --output /tmp/subs.json
```

- Default language: `en`. Pass `--lang zh` or `--lang zh-Hans` for Chinese.
- The script now uses Android player client (avoids JS runtime + PO Token issues), parses WebVTT natively (no `--convert-subs srt`), and has built-in exponential backoff retry on 429 errors.
- If the primary language fails with 429, it auto-falls back to English. Override with `--fallback-lang`.
- If the video has no auto-generated captions, inform the user and stop.

Output: `[{"t": "mm:ss", "s": 123.4, "text": "..."}]`

### Step 2: Capture Keyframes (requires ffmpeg) — ⚠️ SKIP BY DEFAULT

**默认不抓取关键帧。** 原因：关键帧 base64 嵌入 HTML 会消耗 ~60K token（占总 token 56%），且大多数笔记场景不需要截图。只有当用户明确说「截图」「关键帧」「画面」时，才执行此步骤。

需要时运行：

```bash
python3 ~/.hermes/skills/video-notes/scripts/capture_keyframes.py \
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

⚠️ **不要 read_file 读取全量字幕 JSON。** 用采样脚本生成结构化大纲，只读大纲进上下文：

```bash
python3 ~/.hermes/skills/video-notes/scripts/sample_subtitles.py /tmp/subs.json --output /tmp/outline.md
```

脚本逻辑：
- 按时间等距采样（每 ~3 分钟取一条）
- 按信息密度提取关键段落（长度异常/含数字/含专有名词的段落加权）
- 输出结构：`## 00:00-03:00 主题推断` + 代表性文本片段

然后 **只 read_file 大纲文件**（~2K token），据此理解：
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
python3 ~/.hermes/skills/video-notes/scripts/inject_subs.py /tmp/<video-id>-notes.html /tmp/subs.json
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

### Step 5: Inject Subtitles + Save to Vault

**⚠️ 生成 HTML 后立即注入字幕**（不在 LLM 上下文中操作，省 token）：

```bash
python3 ~/.hermes/skills/video-notes/scripts/inject_subs.py /tmp/<video-id>-notes.html /tmp/subs.json
```

Then copy to Obsidian vault:

```bash
cp /tmp/<video-id>-notes.html "<vault-path>/知识库/30.Resources/视频/<sanitized-title>.html"
open /tmp/<video-id>-notes.html
```

- **Vault path**: `/Users/princyzhang/Library/Mobile Documents/iCloud~md~obsidian/Documents/知识太空舱/`
- **Sanitized title**: Remove special chars, keep it short and readable
- Tell the user: save path (both /tmp and vault), subtitle entry count, keyframe count, sections covered.

### Step 6: Convert to Obsidian Markdown

After the HTML is generated, convert it to an Obsidian-flavored Markdown note and save to the vault:

```bash
python3 ~/.hermes/skills/video-notes/scripts/html_to_obsidian.py /tmp/<video-id>-notes.html
```

The script:
- **Auto-fetches the original YouTube video title** via yt-dlp and uses it as H1
- The hero title (e.g. "Run, Don't Walk") becomes a **subtitle blockquote** below H1
- Adds YAML frontmatter with tags, video URL, creation date, and `original-title`
- Converts HTML to clean Markdown (using html2text)
- SVG diagrams are flattened to text descriptions
- **Saves to `知识库/30.Resources/视频/`** in the Obsidian vault by default
- Filename is derived from the original YouTube title (sanitized)
- Pass `--title "Custom Title"` to override, or `--output <path>` for custom path
- Pass `--subfolder` to change the target folder

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

#### Step B2b: Download Video with you-get

`you-get` works without cookies for ≤480p on Bilibili (unlike yt-dlp which requires auth):

```bash
python3 -m you_get --format=dash-flv360-AVC -o /tmp <bilibili_url>
```

- Default format: `dash-flv360-AVC` (lowest quality, sufficient for audio extraction).
- `you-get` also downloads a `.cmt.xml` file containing danmaku (bullet comments) — bonus content.
- If you-get is not installed: `pip install you-get`

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
  - **`small` (461MB)**: ~0.7-1.0x 实时速度（10 分钟视频约 7-10 分钟）。用于英文视频（tiny 英文不可用）或对精度要求极高的中文场景（如需要精确引用原话）。
  - **MPS check**: `python3 -c "import torch; print(torch.backends.mps.is_available())"` — MPS 可用时 tiny 极快。
- **⚠️ MPS 挂死兜底**：如果 whisper 在 MPS 上超时或 hang（即使 `torch.backends.mps.is_available()` = True），立即改用 `--device cpu`。不要反复重试 MPS。见 Pitfall E21。
  - 所有模型缓存在 `~/.cache/whisper/`，首次下载后复用。
  - 详细速度/精度对比见 `references/bilibili-workflow.md`。
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

Output format: `[{"t": "mm:ss", "s": 123.4, "text": "..."}]` — compatible with Steps B5-B7 below (which reference `/tmp/subs.json`).

### Steps B5–B7: Same as YouTube Steps 4–6

After obtaining the subtitle JSON, proceed with the standard workflow:
- **Step B5** → YouTube Step 4: Generate HTML Notes
- **Step B6** → YouTube Step 5: Save HTML to Vault and Open
- **Step B7** → YouTube Step 6: Convert to Obsidian Markdown

⚠️ **Bilibili: remember to save both HTML and Markdown to vault.** After Step B5, copy the HTML to `知识库/30.Resources/视频/` with a sanitized filename. The `html_to_obsidian.py` script in Step B7 handles the Markdown side automatically.

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
- **Network**: Bilibili API and you-get both work from this machine without proxy. yt-dlp does NOT (HTTP 412).
- **Whisper model selection**: See `references/bilibili-workflow.md` for the full model-size-vs-language-vs-duration tradeoff table.
- **长视频转录后的处理**：Whisper 转录 30+ 分钟视频会产生 1000+ 片段。不要逐段读取，用 Python 按时间间隔采样（每 ~3 分钟取一条），快速建立内容结构，再据此生成笔记。

## Xiaoyuzhou FM (小宇宙) Workflow

小宇宙播客不同于 YouTube/Bilibili——它没有视频流也没有自动字幕，但 **show notes（节目笔记）质量极高**，通常包含详细时间轴和概念注释。不需要下载音频或 Whisper 转录——直接从 show notes 提取结构化内容。

### Step X1: Extract Show Notes via Browser

使用 `browser_navigate` 打开播客页面，然后用 `browser_console` 提取 `article` 元素的完整文本：

```javascript
document.querySelector('article') ? document.querySelector('article').innerText : 'no article'
```

这一步获取的内容包含：
- 节目介绍和开场白
- 完整时间轴（`03:22 标题 —— 描述` 格式）
- 概念注释（`📑 猜你想看` 段落：时间戳 + 概念名 + 释义）
- 嘉宾介绍、引用、往期推荐
- 评论区热门留言（`browser_snapshot` 获取的页面快照中也可以提取）

**关键信息提取：**
- 节目标题、主持、嘉宾、时长、播放量、评论数 — 从页面 snapshot 获取
- 时间轴条目 — 解析 `HH:MM:SS 标题` 格式
- 概念词典 — 解析 `📑 猜你想看` 段落中 `时间戳 概念名：释义` 格式
- 精选评论 — 从页面 snapshot 中选取高赞评论

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

**CSS 变量与视频笔记模板保持一致**（`--bg: #1a1a2e` 等）。额外样式：
```css
.tl-item{display:flex;gap:14px;padding:16px 0;border-bottom:1px solid var(--border)}
.tl-ts{font-family:monospace;font-size:12px;color:var(--accent);min-width:70px}
.concept{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px 16px}
.concept-ts{font-size:10px;color:var(--accent);margin-bottom:4px}
.comment{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px 16px}
```

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
plays: 151163
comments: 276
---

# 节目标题

> 播客名 · 集数 · 主持 × 嘉宾 · 时长 · 播放量

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

### Step X5: Save to Vault

播客笔记保存到 `知识库/30.Resources/播客/`（与视频和 B 站的目录分开）：

```bash
mkdir -p "<vault-path>/知识库/30.Resources/播客"
cp /tmp/<episode-slug>-notes.html "<vault-path>/知识库/30.Resources/播客/<sanitized-title>.html"
# Markdown 直接 write_file 写入同路径
```

**Vault path**: `/Users/princyzhang/Library/Mobile Documents/iCloud~md~obsidian/Documents/知识太空舱/`

### Step X6: Deliver

生成 HTML 后用 `open` 在浏览器预览，用 `send_message` 发送 HTML 文件到飞书。

### Xiaoyuzhou-Specific Notes

- **不需要网络代理**：小宇宙页面可直接访问。
- **不需要 yt-dlp / you-get / Whisper / ffmpeg**：完全基于浏览器 DOM 提取 + LLM 处理。
- **show notes 质量决定笔记质量**：小宇宙的 show notes 通常比 B 站更详细（含概念注释），直接利用即可。
- **评论区是宝库**：小宇宙用户评论质量通常很高，选取 5-8 条高赞评论加入笔记。
- **模板独立**：不要复用 `note-template.html` 的字幕/关键帧 JS 逻辑，播客页面结构完全不同。
- **文学文本提取**：当用户询问书中具体段落时，参见 `references/literature-text-extraction.md` — 中文全文网站的搜索与提取技巧。

## Non-小宇宙 Podcast Workflow (Relay FM, etc.)

小宇宙工作流的核心思想（浏览器提取 show notes → 定制 HTML → 手写 MD）同样适用于其他播客平台。但需要注意以下差异：

### Cloudflare 保护

Relay FM 等国际播客网站通常有 Cloudflare 反爬保护，`browser_navigate` 和 `curl` 都会失败。**唯一可用方案是 Bright Data CLI**：

```bash
brightdata scrape "https://relay.fm/cortex/179"
```

> 依赖：`brightdata` CLI 已安装（`brew install brightdata`），免费额度 $7.50/月。余额用 `brightdata budget` 查看。

### Show Notes 稀薄时的补救

部分播客（如 Cortex）的 show notes 只有链接列表，没有小宇宙那种详细时间轴和概念注释。此时需要：

1. **从 show notes 提取链接列表**，识别核心话题和嘉宾的关键文章
2. **用 Bright Data 批量抓取链接文章**（通常 5-8 篇即可覆盖全部话题）：
   ```bash
   brightdata scrape "https://stephango.com/vault"
   brightdata scrape "https://stephango.com/file-over-app"
   # ... etc
   ```
3. **以文章内容为骨架生成笔记**，而不是凭空推测播客对话内容
4. 在笔记末尾注明数据来源（"基于 show notes 及 N 篇相关文章综合整理"）

### 模板适配

非小宇宙播客的 HTML 模板与纯小宇宙播客相同——不需要 `note-template.html` 的字幕/关键帧区域。保持：
- 侧边导航 + scroll-spy
- Hero 区 + 核心总结 + 主题章节 + SVG 图表
- 概念词典
- 参考链接
- 无字幕面板、无关键帧

## Xiaohongshu (小红书) Workflow

小红书同时支持图文和视频帖子。通过 `__INITIAL_STATE__` JSON 直接获取结构化数据（无需浏览器），支持 xhslink.com 短链自动 302 跟踪。

**前置条件**：`~/cookies.json`（从 Chrome 导出的小红书登录 cookies，见步骤 0）

### Step S0：检查 Cookies

1. 检查 `~/cookies.json` 是否存在
2. 如果不存在，告知用户导出方法（F12 Console → `copy(JSON.stringify(...))` → 保存到 `~/cookies.json`），终止等待用户完成

### Step S1：解析链接 + 获取帖子数据

**一键脚本**（处理标准链接和短链，自动跟随 302）：

```python
import json, urllib.request, ssl, re, sys
from urllib.parse import urlparse, parse_qs

with open('/Users/princyzhang/cookies.json') as f:
    cookies = json.load(f)
cookie_str = '; '.join(f\"{c['name']}={c['value']}\" for c in cookies)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
ua = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

input_url = '<用户提供的链接>'

# 短链 302 跟踪
if 'xhslink.com' in input_url:
    req = urllib.request.Request(input_url)
    req.add_header('User-Agent', ua)
    resp = urllib.request.urlopen(req, timeout=15, context=ctx)
    real_url = resp.geturl()
else:
    real_url = input_url

# 提取帖子 ID（24 位 hex）
path = urlparse(real_url).path
m = re.search(r'/([0-9a-f]{24})', path)
post_id = m.group(1)
query = parse_qs(urlparse(real_url).query)
xsec = query.get('xsec_token', [''])[0]
req_url = f'https://www.xiaohongshu.com/explore/{post_id}?xsec_token={xsec}&xsec_source=pc_feed'

# 请求页面 + 解析 __INITIAL_STATE__
req = urllib.request.Request(req_url)
req.add_header('Cookie', cookie_str)
req.add_header('User-Agent', ua)
resp = urllib.request.urlopen(req, timeout=15, context=ctx)
html = resp.read().decode('utf-8', errors='ignore')

if 'window.__INITIAL_STATE__' not in html:
    print("ERROR: cookies expired — 请重新导出 ~/cookies.json")
    sys.exit(1)

m = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.+?\})\s*</script>', html, re.DOTALL)
raw = m.group(1).replace('undefined', 'null')
data = json.loads(raw)
note_detail_map = data.get('note', {}).get('noteDetailMap', {})
key = list(note_detail_map.keys())[0]
note = note_detail_map[key].get('note', {})

# 帖子字段：title, desc, type ('normal'/'video'), time(ms), user,
#   imageList[{urlDefault,w,h}], video, interactInfo, tagList, ipLocation
```

### Step S1b：下载图片 + OCR 识别（所有帖子）

无论图文还是视频帖子，只要有图片就全部下载并对每张图做 OCR。识别结果追加到 `desc` 中用于后续整理。

**图片存储路径**：`知识库/30.Resources/视频/img/{post_id}/`（Obsidian vault 内，便于引用）

```python
import os, urllib.request

img_dir = f'{VAULT}/知识库/30.Resources/视频/img/{post_id}'
os.makedirs(img_dir, exist_ok=True)

# Phase 1: 下载所有图片
image_paths = []
for i, img in enumerate(note.get('imageList', [])):
    url = img['urlDefault']
    # XHS CDN URLs often lack clean extensions — default to .jpg
    path_part = url.split('?')[0]
    ext = path_part.rsplit('.', 1)[-1] if '.' in path_part.rsplit('/')[-1] else 'jpg'
    if ext not in ('jpg','jpeg','png','gif','webp','heic'):
        ext = 'jpg'
    local_path = f'{img_dir}/{i+1:02d}.{ext}'
    
    req = urllib.request.Request(url)
    req.add_header('User-Agent', ua)
    req.add_header('Referer', 'https://www.xiaohongshu.com/')
    with open(local_path, 'wb') as f:
        f.write(urllib.request.urlopen(req, timeout=30, context=ctx).read())
    image_paths.append(local_path)
    print(f'  [{i+1}/{len(note["imageList"])}] Downloaded: {local_path}')
```

**Phase 2: 批量 OCR**（单一进程，模型只加载一次，避免 subprocess 重复加载。图片 >10 张只 OCR 前 10 张）

```python
# ⚠️ 必须用 conda Python：/opt/anaconda3/bin/python3
# ⚠️ ocr() 已废弃 — 用 predict()；结果字段：r[0].get('rec_texts', [])
from paddleocr import PaddleOCR
ocr = PaddleOCR(lang='ch')  # 模型只加载一次

limit = min(len(image_paths), 10)
ocr_texts = []
for i in range(limit):
    r = ocr.predict(image_paths[i])
    texts = r[0].get('rec_texts', [])
    ocr_text = '\n'.join(texts)
    if ocr_text.strip():
        ocr_texts.append(f'[图{i+1}]\n{ocr_text}')
    print(f'  [{i+1}/{limit}] OCR: {len(ocr_text)} chars')
```

**Phase 3: 合并 OCR 结果**

```python
full_text = note.get('desc', '')
if ocr_texts:
    full_text += '\n\n---\n【图片OCR识别】\n' + '\n\n'.join(ocr_texts)
note['_ocr_text'] = full_text  # 用于后续整理
```

### Step S2：视频帖子 — 转录（仅 type == 'video'）

仅当 `note['type'] == 'video'` 时执行。**先快速检查字幕可用性**：`media.get('mediaV2')` 存在 → 解析其 JSON 中的 `subtitles` → 有 zh-CN SRT URL → 直接下载 SRT。**试一次，不存在就立即 fallback**（不要反复搜索，见 Pitfall E25）。

转录方案（按优先级）：

1. **首选 `mlx_whisper`**（MLX 优化，Mac M 系列最快）：

```python
stream = note['video']['media']['stream']
for codec in ['h264', 'h265', 'av1']:
    if codec in stream and stream[codec]:
        master_url = stream[codec][0]['masterUrl']
        break
```

```python
# 下载视频
stream = note['video']['media']['stream']
for codec in ['h264', 'h265', 'av1']:
    if codec in stream and stream[codec]:
        master_url = stream[codec][0]['masterUrl']
        break

import urllib.request
req = urllib.request.Request(master_url)
req.add_header('User-Agent', ua)
req.add_header('Referer', 'https://www.xiaohongshu.com/')
with open(f'/tmp/xhs_video.mp4', 'wb') as f:
    f.write(urllib.request.urlopen(req, timeout=60, context=ctx).read())
```

```bash
# 提取音频
ffmpeg -y -i /tmp/xhs_video.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 /tmp/xhs_audio.wav
```

```bash
# 转录：先试 mlx_whisper，失败则 fallback openai-whisper CPU
python3 -c "
try:
    import mlx_whisper
    result = mlx_whisper.transcribe('/tmp/xhs_audio.wav',
        path_or_hf_repo='mlx-community/whisper-large-v3-turbo', language='zh', verbose=False)
    text = result['text']
except (ImportError, Exception):
    import subprocess, sys
    subprocess.run([sys.executable, '-m', 'whisper', '/tmp/xhs_audio.wav',
        '--model', 'tiny', '--language', 'Chinese', '--output_dir', '/tmp',
        '--output_format', 'txt', '--device', 'cpu'], check=True)
    with open('/tmp/xhs_audio.txt') as f:
        text = f.read()
with open('/tmp/xhs_transcript.txt', 'w') as f:
    f.write(text.strip())
print(f'Transcribed: {len(text)} chars')
" 2>&1

# 清理
rm -f /tmp/xhs_video.mp4 /tmp/xhs_audio.wav /tmp/xhs_audio.txt
```

图文帖子（`type == 'normal'`）跳过此步骤。

### Step S3：生成 HTML 笔记

小红书帖子不用 `note-template.html`（该模板为视频/字幕设计）。定制 HTML，深色主题与视频笔记统一：

| 特性 | 说明 |
|------|------|
| 深色主题 | CSS 变量与视频笔记一致（`--bg: #1a1a2e`） |
| Hero 区 | 标题、作者、互动数据、标签 chips、金句引用 |
| Thiel 式总结 | 直接、反直觉、2-3 句给判断 |
| 图片画廊 | 从 `imageList` 渲染，优先使用本地路径 `img/{post_id}/`，回退 `urlDefault` |
| 视频转录区 | 仅视频帖子：整理后的转录文本 |
| 帖子属性 | 来源、ID、链接、日期、互动数据 |
| 无侧边导航 | 单帖内容无需多章节导航 |
| 无字幕面板 | 小红书没有时间戳字幕 |
| 无关键帧 | 不需要视频截图 |

**HTML 保存路径**：`知识库/30.Resources/视频/<sanitized-title>.html`

> 视频帖子的完整 HTML 模板和示例见 `references/xhs-html-template.md`。

### Step S4：生成 Obsidian Markdown

Thiel 式写作风格——直接、反直觉、一句话给判断。笔记是决策工具，不是知识库。用户扫一眼就能决定：深挖还是跳过。

**文件结构**（无 YAML frontmatter）：

```markdown
# 一句话核心洞察（反直觉的判断）

核心论点，2-3句话。直接给出判断。
不废话，不铺垫。

**与我的关联：** 一句话。结合用户背景说清关系。

**值得深挖吗：** 是/否。一句话理由。

> [!tip]- 详情
> 从 desc 和视频转录提炼的结构化内容

> [!info]- 笔记属性
> - **来源**: 小红书 · 作者名
> - **帖子ID**: xxx
> - **链接**: 原始链接
> - **日期**: YYYY-MM-DD
> - **类型**: image / video
> - **互动**: N赞 / N收藏 / N评论
> - **标签**: tag1, tag2
```

**关键约束**：
- 折叠区域外可见内容不超过 6 行
- 标题必须是洞察/判断
- ⚠️ **图片 wikilink 绝对不要用 `../img/`**：MD 文件在 `视频/` 目录下，图片在 `视频/img/` 目录下，所以正确路径是 `![[img/{post_id}/01.jpg]]`（同级子目录），不是 `![[../img/...]]`（会跑到 `30.Resources/img/` 导致 Obsidian 找不到图）

**MD 保存路径**：`知识库/30.Resources/视频/<sanitized-title>.md`（与 HTML 同目录，与原 video-notes 保持一致）

### Step S5：打开预览

```bash
open /tmp/xhs_{post_id}.html
```

### Xiaohongshu-Specific Notes

- **Cookies 是唯一认证方式**：不需要登录态以外的任何 token
- **图文帖子无需 Whisper**：直接解析 desc + 图片 OCR 结果即可
- **图片全部落地 + OCR**：所有图片下载到 `知识库/30.Resources/视频/img/{post_id}/`，PP-OCRv5 逐张识别，结果合并入 desc
- **链接处理统一**：短链只需多一步 302 跟踪，`resp.geturl()` 拿真实 URL
- **保存路径统一**：所有平台（YT/B站/小宇宙/小红书）的 MD 和 HTML 都存入 `知识库/30.Resources/视频/`

### 批量提取（原 xhs-batch）

多个小红书链接时，对每个链接执行 Step S1~S4，间隔 3 秒防反爬，最后汇总报告：

```
✅ 成功 N 条
❌ 失败 M 条

1. <文件名> — <一句话摘要>
2. ...
```

### 分析已保存内容（原 xhs-analyze）

读取 `知识库/30.Resources/视频/` 下所有 MD，按关键词搜索或总览分析：
- 教程/攻略类 → 提炼步骤清单 + 对比
- 知识/科普类 → 关键知识点 + 结构化笔记
- 总览（无参数）→ 主题分布 + 高频标签 + 推荐深入整理的方向

## WeChat Article (微信公众号) Workflow

微信公众号文章没有视频/音频，但图文内容质量高。核心挑战：**微信对图片 URL 做了 JS 加密混淆**，静态 HTML 中的 `data-src` 是 JS 拼接字符串（`').concat(r,'`），curl 直接抓取会丢失所有配图。

### Step W0：前置知识

- 微信文章图片的 `data-src` 在静态 HTML 中不可直接使用——只有浏览器执行 JS 后 `src` 属性才会暴露真实 `mmbiz.qpic.cn` URL
- 文章可能有 0–15+ 张配图，必须全部保留
- 用户可选择是否同时生成 ProcessOn 脑图

### Step W1：提取内容（必须用浏览器）

```bash
# 用移动端微信 UA 打开文章
browser_navigate(url="https://mp.weixin.qq.com/s/...")
```

等页面渲染完成后，用 `browser_console` 提取：

```javascript
// 1. 提取标题
document.querySelector('#activity-name')?.innerText

// 2. 提取作者/公众号名
document.querySelector('#js_name')?.innerText

// 3. 提取正文（含图片位置）
document.querySelector('#js_content')?.innerText

// 4. 提取所有内容图片的真实 URL
Array.from(document.querySelectorAll('img[src*="mmbiz.qpic.cn"]'))
  .map(i => i.src)
  .filter(u => !u.includes('qlogo'))  // 排除头像
```

**关键点**：
- 只用浏览器渲染后的页面，不要用 curl 抓静态 HTML
- 正文文本从 `browser_snapshot` 获取即可
- 图片 URL 必须从 `browser_console` 提取（DOM 中的 `src` 属性）

### Step W2：下载图片

```python
import urllib.request, ssl, os

ctx = ssl.create_default_context()
for i, url in enumerate(unique_img_urls):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = urllib.request.urlopen(req, timeout=15, context=ctx).read()
    with open(f"/tmp/weixin-imgs/{i:02d}.png", 'wb') as f:
        f.write(data)
```

- 去重方式：按 URL 路径中的 hash ID 去重（`url.split('/')[-2]`）
- 图片格式统一保存为 `.png`（微信 CDN 默认输出 PNG）

### Step W3：生成 Obsidian Markdown

文章笔记存入 `知识库/30.Resources/文章/`，图片存入同目录 `assets/` 子文件夹。

```markdown
# 文章标题

> 来源：公众号「XXX」 | 原文链接：URL

---

## 🧠 脑图总览（如用户要求生成）

![[../30.Resources/文章/assets/xxx-脑图.png]]

---

## 📄 原文

[全文逐字保留]

---

## 🖼️ 原文配图

![[../30.Resources/文章/assets/article-img-01.png]]

...

---

## 📌 一句话

[核心观点的精炼总结]
```

**保存路径**：
- MD：`知识库/30.Resources/文章/<文章标题>.md`
- 图片：`知识库/30.Resources/文章/assets/<文章标题>-img-NN.png`
- 脑图（可选）：`知识库/30.Resources/文章/assets/<文章标题>-脑图.png`

### Step W4（可选）：生成 ProcessOn 脑图

如果用户要求生成脑图，使用 `processon-mindmap-generator` skill：
1. 按 skill 规范做云端版本检查
2. 从文章提炼结构化大纲
3. 调用 `processon_mindmap_client.py` 生成脑图
4. 下载图片到 assets 目录
5. 在 MD 中嵌入 wikilink

### WeChat-Specific Notes

- **图片是最大坑**：静态 HTML 里 `data-src` 不可用，必须浏览器渲染后提取
- **文章无原始标题标签**：`<title>` 被 JS 动态设置，从 `#activity-name` 获取
- **无需视频/音频处理**：没有 Whisper、yt-dlp、ffmpeg 依赖
- **可结合 ProcessOn**：文章适合生成结构化脑图

## Quality Guidelines

- **Summary is mandatory** — always write the executive summary; it's the first thing readers see.
- **Keyframes are optional** — skip by default unless the user explicitly asks for screenshots. Each frame adds ~30KB base64 to the HTML, ballooning token usage ~56% for negligible reading value.
- **Depth over breadth** — 4–7 well-developed sections beat 12 shallow ones.
- **Diagrams are mandatory** when content has comparisons, progressions, or architectures.
- **Language matching** — write in the same language as the user's request, regardless of the video's language.

## Pitfalls Fixed (Hermes Adaptation)

These issues were discovered during real-world testing and are now resolved in the scripts:

| # | Pitfall | Severity | Fix |
|---|---------|----------|-----|
| 1 | yt-dlp requires JS runtime → "video not available" | 🔴 Blocker | Use `--extractor-args youtube:player_client=android` in both scripts |
| 2 | Web client requires PO Token → 429 errors | 🔴 Blocker | Android player client bypasses PO Token entirely |
| 3 | Subtitle script didn't pass JS runtime args | 🔴 Blocker | Fixed — Android client is now default in both scripts |
| 4 | Chinese (zh-Hans) persistent 429 | 🟡 Partial | Auto-fallback to English; use `--fallback-lang` to override |
| 5 | yt-dlp produces VTT not SRT → parse failure | 🟡 Blocker | Added `parse_vtt_or_srt()` that handles both formats; removed `--convert-subs srt` |
| 6 | `--convert-subs srt` triggers extra 429 request | 🟢 Minor | Removed — parse VTT directly |
| 7 | Keyframe download silently skipped on network error | 🟡 Usability | Network pre-check + clear error categorization (RATE_LIMITED / NETWORK_UNREACHABLE / etc.) |
| 8 | No retry on transient failures | 🟢 Minor | Exponential backoff retry (up to 3 attempts) on 429 and other transient errors |

## Environment-Specific Pitfalls

| # | Pitfall | Workaround |
|---|---------|------------|
| E1 | YouTube 不可达（curl/google.com 超时），但 yt-dlp 字幕 API 可通 | 字幕提取正常；关键帧视频下载不可用，跳过即可 |
| E2 | curl 网络预检会卡死（无代理时 `--connect-timeout` 无效） | 已移除 `check_network()` 的 curl 实现，yt-dlp 下载自带错误处理 |
| E3 | YouTube 在中国大陆被墙，直连超时 | 设置代理环境变量后 yt-dlp 可通：`export https_proxy=http://127.0.0.1:7897 http_proxy=http://127.0.0.1:7897`。字幕提取和 `html_to_obsidian.py`（自动 fetch 标题）都需要代理。先用 `curl -sI --max-time 5 -x http://127.0.0.1:7897 https://www.youtube.com` 验证代理可用。 |
| E4 | Whisper 模型下载慢 | 模型缓存在 `~/.cache/whisper/`，首次下载后复用；tiny/small 模型约 460MB
| E5 | `html_to_obsidian.py` 对 B 站视频自动 fetch 标题会失败（yt-dlp HTTP 412） | B 站视频必须传 `--title`，用 B1 步骤获取的标题 |
| E6 | `note-template.html` 的 JS 中硬编码了 YouTube 链接格式，B 站视频点击字幕会跳转 404 | 生成 HTML 后替换 YouTube URL 为 Bilibili URL（见 Steps B5-B7 的模板适配说明） |
| E7 | `whisper` 命令不存在（openai-whisper 未安装或不在 PATH 中） | `pip install openai-whisper`；若 CLI 不可用，使用 `python3 -m whisper` 代替 `whisper` |
| E8 | `you-get`、`whisper`、`html2text`、`beautifulsoup4` 装在 conda Python 中，hermes venv 的 `python3` 找不到模块 | 全文统一使用 conda Python 路径（`/opt/anaconda3/bin/python3`）：包括 B站API下载、Whisper 转录、`html_to_obsidian.py` 转换。用 `which python3` 确认当前活跃环境 |
| E9 | HTML 只存 /tmp 容易丢失，下次找不到 | 生成 HTML 后同时 `cp` 到 `知识库/30.Resources/视频/`，与 Markdown 并列存储 |
| E10 | B 站 API / 网页间歇性 Connection reset，`b23.tv` 短链和 `api.bilibili.com` 均不可达 | 直接问用户索要 BV 号（分享链接中 `BVxxxxxxxxx` 那串）。拿到 BV 号后用 B1 的 API 流程重试——API 偶尔能通。若 API 也 reset，等几分钟重试。不要反复用不同方式攻击 B 站。 |
| E11 | `curl | python3` 管道被 tirith 安全扫描器拦截（HIGH risk） | 改用 `execute_code` + `urllib.request`（见 cn-web-search 技能的执行方式章节）。curl 直接管道到解释器永远不会通过审批。 |
| E12 | 小宇宙播客的 `html_to_obsidian.py` 会失败（内部调用 yt-dlp 获取标题，对小宇宙 URL 无效） | 小宇宙播客**不要用** `html_to_obsidian.py`。直接手写 Markdown 文件，title 从 browser snapshot 的 `<h1>` 获取。 |
| E13 | 用户询问小说原文段落（非视频/播客），线上中英文源均被付费墙/Cloudflare/地理封锁挡掉 | 按优先级查找：Obsidian vault → session history → 中文源 → Gutenberg → 凭记忆。详见 `references/content-sourcing-pitfalls.md`。不要死磕一个源——三连失败立即切换到下一级。 |
| E14 | 小红书分享链接的内容提取 | 已整合到 video-notes 技能中（见 Xiaohongshu Workflow）。支持标准链接 + xhslink.com 短链 302 跟踪，需 `~/cookies.json` 认证。统一存入 `知识库/30.Resources/视频/`。 |
| E15 | 用户偏好/评价标准不在 Hermes 记忆中，session_search 也找不到 | 查 OpenClaw workspace 文件：`~/.openclaw/workspace/TOOLS.md` → `MEMORY.md` → `memory/` 目录 → `skills/doudou/MEMORY.md`。详见 `references/content-sourcing-pitfalls.md`。 |
| E16 | Whisper 转录 30+ 分钟中文视频产生 1000+ 片段，全文读取不现实 | 用 Python 脚本按时间间隔采样（每 2-3 分钟取一条），快速建立内容结构和主题边界，再据此生成笔记。不要逐段读取全量字幕 JSON。 |
| E18 | `sample_subtitles.py` 对密集对话类视频过于稀疏（每段 ~1s，采样仅 ~50 条），难以把握核心论点 | 采样后用 `execute_code` + Python 做时间区间文本聚合：将字幕按 3-5 分钟窗口 `" ".join()` 拼接成连续文本块，一次性获得完整上下文。见 `references/bilibili-workflow.md` 的「密集对话采样补充」章节。不要直接用 read_file 读全量字幕 JSON（仍然太大）。 |
| E17 | B站视频用 you-get 或 yt-dlp 均返回 HTTP 412，2026年6月实测两者均不可用 | **不要反复尝试**。改用 B 站 API：`api.bilibili.com/x/player/playurl?bvid={BV}&cid={CID}&qn=16` 获取 `durl[0].url`，再用 `urllib.request` + Referer 下载。详见 `references/bilibili-api-download.md`。需统一用 conda Python `/opt/anaconda3/bin/python3`。 |
| E19 | "small 太慢必须用 tiny" 的假设只在纯 CPU 时成立 | M2+ Mac 开 MPS 加速后 small 跑 0.7x 实时（比实时还快）。先检查 `torch.backends.mps.is_available()`，MPS 可用时默认 small。详见 `references/bilibili-workflow.md` 的速度对照表。 |
| E20 | Whisper 中文转录输出繁体字（如「為什麼」「資訊」） | Whisper 的 `Chinese` 语言码不区分简繁，tiny/small 模型训练数据偏繁体。Step B4 已默认加入 `zhconv.convert(text, 'zh-cn')` 繁→简转换。手动处理旧文件：`python3 -c "from zhconv import convert; print(convert('繁体文本', 'zh-cn'))"` |
| E21 | Whisper 在 MPS 上挂死或极慢（`--fp16 False` 仍超时 180s） | 即使 `torch.backends.mps.is_available()` = True，Whisper 在 MPS 后端上仍可能 hang 或极慢。**立即改用 `--device cpu`**——对 tiny/small 模型，CPU 在此情况下反而比挂死的 MPS 快得多。不要反复重试 MPS。 |
| E22 | XHS 图片 OCR 首张超时（PP-OCRv5 子进程模式） | 不要用 subprocess.run() 每张图起新 Python。改用单一进程：加载 PaddleOCR 一次，循环调用 `predict()`。见 `paddleocr-local` skill 的批量模式。 |
| E23 | `ocr.ocr()` 废弃 → 结果为 OCRResult dict，非旧嵌套列表 | paddleocr >= 3.6 弃用 `ocr()`。用 `predict()`。结果通过 `r[0].get('rec_texts', [])` 访问，不是 `result[0]` 嵌套列表。**不要用 `hasattr(item, 'rec_texts')`** — `rec_texts` 是 dict key，不是属性。检测 OCRResult: `isinstance(r[0], dict) and 'rec_texts' in r[0]`。 |
| E24 | XHS MD 图片 wikilink 写成 `![[../img/...]]` → Obsidian 找不到图 | MD 文件在 `视频/` 目录下，图片在 `视频/img/{post_id}/` 下，是同级子目录。必须用 `![[img/{post_id}/01.jpg]]`，不能用 `../img/`（`../` 会跑到 `30.Resources/` 层，img 目录不在那里）。 |
| E25 | S1 提取的 `__INITIAL_STATE__` note 数据中 `mediaV2` 字段不可靠（有时在 `note.video.media` 下，有时不存在）→ 字幕 URL 提取失败，反复搜索浪费回合 | `__INITIAL_STATE__` 和 SSR（`__SETUP_SERVER_STATE__`）是两套数据。SRT 字幕 URL 在 SSR 的 `mediaV2.subtitles` 中，但 S1 脚本只提取 `__INITIAL_STATE__`。**不要反复尝试从 note JSON 找字幕**——试一次 `media.get('mediaV2')`，不存在就立即走 S2 视频下载+Whisper 路线。9 分钟以内的视频用 Whisper tiny CPU 约 1-2 分钟，比反复搜字幕更快。 |
| E26 | 微信文章 curl 抓取静态 HTML — 图片全部丢失（`data-src` 是 `').concat(r,'` JS 拼接） | 必须用 `browser_navigate` 打开文章，等 JS 渲染后再用 `browser_console` 提取：`document.querySelectorAll('img[src*=\"mmbiz.qpic.cn\"]')`。不要用 curl、requests、urllib 直接抓。图片去重用 `url.split('/')[-2]`（路径 hash ID）。 |
