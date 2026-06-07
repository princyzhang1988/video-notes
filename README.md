# video-notes

> **Forked from [kaimomo99/video-notes](https://clawhub.ai/kaimomo99/video-notes)** — 感谢原作者的优秀工作！

把 YouTube / Bilibili 视频 / 小宇宙播客变成精美的结构化笔记。粘贴一个链接，几分钟后你会得到一份带图表和逐字稿的精美文档。

## 效果预览

输入：YouTube / Bilibili / 小宇宙 FM 链接
输出：自包含的 HTML 文档 + Obsidian Markdown，包含：

- **核心论点总结**（~300 字）：一句话主张 + 主线论据 + 关键预言
- **章节结构笔记**：SVG 图表、对比卡片、时间线
- **关键帧画廊**（可选）：自动截取重要时刻的视频截图
- **全文字幕搜索**：实时高亮，点击跳转原视频时间点

## 与原版的区别

本版本在 [kaimomo99/video-notes](https://clawhub.ai/kaimomo99/video-notes) 的基础上调整了：
1、默认跳过关键帧的采集（节约约56%的token）
2、优化了字幕采集与注入（节约约8%的token）
3、md文件的生成，方便obsidian等知识库的集成

| 调整 | 说明 |
|------|------|
| 🎙️ **小宇宙 FM 支持** | 从 show notes 提取结构化笔记，无需音频下载 |
| 🎤 **Whisper 转录回退** | B 站无字幕视频自动用 Whisper 转录 + 繁→简转换 |
| 📊 **采样大纲** | 不读全量字幕（省 token），用智能采样建立内容结构 |
| 💉 **字幕注入** | 生成 HTML 后再注入字幕 JSON，避免占用 LLM 上下文 |
| ⚡ **并行转录** | 可选的多进程 Whisper 加速（长视频适用） |
| 🇨🇳 **B 站深度优化** | API 直链下载、弹幕解析、zhconv 繁转简 |

## 使用方式

直接把youtube、bilibili的视频扔给你的Agent既可。

## 依赖

- Python 3.8+
- `yt-dlp`（脚本自动安装）
- `ffmpeg`（关键帧截图需要，可选）
- `openai-whisper`（B 站无字幕视频转录，可选）

macOS 安装 ffmpeg：

```bash
brew install ffmpeg
```

## 适用场景

| 场景 | 说明 |
|------|------|
| 技术演讲 / 大会分享 | AI Ascent、TED、Google I/O 等 |
| 网课 / 公开课 | Coursera、MIT OpenCourseWare |
| 播客 / 长访谈 | 小宇宙 FM、Lex Fridman、各类深度对话 |
| 产品发布会 | WWDC、OpenAI DevDay 等 |
| 论文解读 | 作者在 YouTube 讲自己的论文 |
| B 站知识视频 | 科技区、知识区、访谈类内容 |

## 文件结构

```
video-notes/
├── SKILL.md                         # Skill 定义和工作流
├── README.md                        # 本文件
├── skill.json                       # 元数据
├── LICENSE                          # MIT
├── CHANGELOG.md                     # 版本历史
├── scripts/
│   ├── extract_subtitles.py         # 字幕提取（YouTube, Bilibili）
│   ├── capture_keyframes.py         # 关键帧识别和截取
│   ├── sample_subtitles.py          # 智能采样生成大纲
│   ├── inject_subs.py               # 字幕注入 HTML（省 token）
│   ├── html_to_obsidian.py          # HTML → Obsidian Markdown 转换
│   └── whisper_parallel.py          # 并行 Whisper 转录（实验性）
├── assets/
│   └── note-template.html           # HTML 文档模板
└── references/
    ├── bilibili-workflow.md         # B 站工作流详细参考
    ├── bilibili-api-download.md     # B 站 API 直链下载方案
    ├── dense-dialogue-supplement.md # 密集对话采样补充
    ├── literature-text-extraction.md # 文学文本提取技巧
    └── literature-text-sourcing.md  # 文学作品原文查找策略
```

## 致谢

本 skill 基于 [kaimomo99/video-notes](https://clawhub.ai/kaimomo99/video-notes) 修改而来。原版提供了 YouTube + Bilibili 基础字幕提取和精美的 HTML 模板。感谢 kaimomo99 的开源贡献！

## License

MIT — 详见 [LICENSE](./LICENSE)
