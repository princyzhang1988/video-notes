# Literature Full-Text Extraction

When the user asks about a specific passage in a book they're reading and the Obsidian vault doesn't have detailed chapter notes, extract the full text online for analysis.

## Workflow

1. **Search for the text** using 360 search (Baidu often has captchas):
   ```
   https://m.so.com/s?q=书名+作者+第X部+第X章
   ```
   Chinese full-text literature sites include: `diancang.xyz` (中华典藏), `zhonghuadiancang.com`, QQ阅读.

2. **Navigate to the chapter page** via `browser_navigate`.

3. **Extract full text** via `browser_console`:
   ```javascript
   document.querySelector('article') ? document.querySelector('article').innerText : document.body.innerText.substring(0, 15000)
   ```

4. **Analyze and summarize** the passage, focusing on:
   - Dialogue content and subtext
   - Character motivations and power dynamics
   - Plot-relevant information revealed
   - Connections to the novel's broader themes

## Notes

- 360 search (`m.so.com`) is the most reliable for Chinese literature queries; Baidu often shows captchas in headless mode.
- `diancang.xyz` URL structure is unpredictable; always search rather than guessing URLs.
- When the passage is long, extract in chunks or use `substring(0, 15000)` for the first pass.
- This technique applies to any work in the public domain or available on Chinese full-text sites.
