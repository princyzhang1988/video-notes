# Changelog

## [1.6.0] - 2026-06-07

### Added
- 小宇宙 FM 播客支持（show notes 提取 → 定制 HTML → 手写 MD）
- `sample_subtitles.py`：智能采样生成大纲，省 token
- `inject_subs.py`：字幕注入 HTML（后处理，不占 LLM 上下文）
- `whisper_parallel.py`：多进程并行 Whisper 转录（实验性）
- B 站 API 直链下载方案（`references/bilibili-api-download.md`）
- `html_to_obsidian.py`：HTML → Obsidian Markdown 转换
- B 站 Whisper 转录后的 zhconv 繁→简转换
- 密集对话采样补充方案（`references/dense-dialogue-supplement.md`）
- Relay FM 等非小宇宙播客工作流

### Changed
- 字幕提取使用 Android player client（避免 JS runtime + PO Token 问题）
- 直接解析 VTT 格式（不再需要 `--convert-subs srt`）
- 字幕提取添加指数退避重试
- 语言回退：中文 429 → 自动回退英文
- 关键帧默认跳过（省 token），用户明确要求时才抓取
- 内容理解改为采样大纲模式（不读全量字幕）

### Fixed
- yt-dlp "video not available" → Android client bypass
- 429 rate limiting → exponential backoff + language fallback
- VTT 解析失败 → 统一 VTT/SRT 解析器
- 关键帧下载静默失败 → 网络预检 + 错误分类
- B 站 you-get/yt-dlp HTTP 412 → API 直链下载

## [1.0.0] - 2026-05-21

### Added (original by kaimomo99)
- `extract_subtitles.py`: YouTube 字幕提取和去重
- `capture_keyframes.py`: 关键帧识别和截取
- `assets/note-template.html`: 自包含 HTML 模板（深色主题、侧边导航、scroll-spy、SVG 图表、关键帧画廊、字幕搜索）
- `SKILL.md`: 完整工作流文档
