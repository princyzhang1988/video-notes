# Content Sourcing Pitfalls

Recurring patterns when trying to extract content from Chinese platforms.

## Xiaohongshu (小红书)

### Problem
All standard access methods fail consistently:
| Method | Error | Reason |
|--------|-------|--------|
| Browser (remote server IP) | 300012: IP 存在风险 | Server-side IP block |
| Bright Data scrape | `bad_endpoint: robots.txt` | Immediate access blocked |
| Bright Data `--mobile` | `bad_endpoint: robots.txt` | Same restriction |
| API (`/api/sns/web/v1/feed`) | `jarvis-gateway-default 500` | Requires authenticated session |
| xhslink.com redirect + xsec_token | 300012 or 500 | Token expires, IP flagged |

### Workaround
- **Only reliable path**: User screenshots/screen-records content → OCR (paddleocr-local) or Whisper transcription
- Content is platform-locked and effectively inaccessible to automated tools
- Don't waste turns retrying different access methods — inform user immediately and ask for direct content

## Literature / Novel Full-Text Sources

### Problem
Chinese full-text novel sites are heavily gated:
| Source | Status |
|--------|--------|
| 99csw.com / 99lib.net | Cloudflare challenge, timeout |
| QQ阅读 (book.qq.com) | Paywall — "开会员，本书免费读" |
| diancang.xyz (中华典藏) | Incomplete chapter coverage on some novels |
| Gutenberg (English translations) | Available but may not match Chinese chapter numbering |

### Workaround
1. First check Obsidian vault for user's own notes (`session_search` for past discussions)
2. Try 360 search for "中华典藏 + 书名 + 章节" 
3. Check Gutenberg for English translation (note: chapter numbering differs from Chinese editions)
4. Use domain knowledge only as last resort — clearly state when working from memory

## Cross-Workspace Knowledge Retrieval

### Problem
User preferences and criteria may be stored in OpenClaw workspace files (`TOOLS.md`, `MEMORY.md`, `memory/YYYY-MM-DD.md`), not in Hermes memory or session history.

### Pattern
When Hermes `session_search` and `memory` fail to find user-stated preferences:
1. Check `~/.openclaw/workspace/TOOLS.md` — environment-specific configs, writing preferences
2. Check `~/.openclaw/workspace/MEMORY.md` — long-term OpenClaw memory
3. Check `~/.openclaw/workspace/memory/` — daily memory files
4. Check `~/.openclaw/workspace/skills/doudou/MEMORY.md` — subagent memory

## Platform-Specific Search

### Preferred Chinese search engine
- **360 搜索** (`m.so.com`) — headless browser accessible, no captcha
- **Baidu** — frequent captcha in headless environments
- Use `&src=news` parameter on 360 for news/articles mode
