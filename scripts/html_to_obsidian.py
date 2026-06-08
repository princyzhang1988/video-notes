#!/usr/bin/env python3
"""
Convert video-notes HTML output to Obsidian-flavored Markdown.

Usage:
    python3 html_to_obsidian.py <input.html> [--title "Original YouTube Title"] [--output <path>]

If --title is not provided, fetches the original YouTube title via yt-dlp.
Saves to Obsidian vault under 知识库/30.Resources/视频/ by default.
Requires: html2text, beautifulsoup4
"""

import sys
import os
import re
import json
import argparse
import subprocess
import html2text
from bs4 import BeautifulSoup


# ── Obsidian vault paths ──
DEFAULT_VAULT = os.path.expanduser(
    "~/Library/Mobile Documents/iCloud~md~obsidian/Documents/知识太空舱"
)
DEFAULT_SUBFOLDER = "知识库/30.Resources/视频"


def ensure_deps():
    """Install html2text, bs4 if missing."""
    try:
        import html2text  # noqa
        import bs4  # noqa
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "html2text", "beautifulsoup4", "-q",
             "--break-system-packages"],
            stderr=subprocess.DEVNULL,
        )


def ensure_yt_dlp():
    """Ensure yt-dlp is available."""
    try:
        import yt_dlp  # noqa
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "yt-dlp", "-q",
             "--break-system-packages"],
            stderr=subprocess.DEVNULL,
        )


def fetch_youtube_title(url: str) -> str | None:
    """Fetch the original YouTube video title via yt-dlp."""
    ensure_yt_dlp()
    try:
        result = subprocess.run(
            [sys.executable, "-m", "yt_dlp",
             "--no-download", "--print", "title",
             "--extractor-args", "youtube:player_client=android",
             "--quiet",
             url],
            capture_output=True, text=True, timeout=30
        )
        title = result.stdout.strip()
        if title and result.returncode == 0:
            return title
    except (subprocess.TimeoutExpired, Exception) as e:
        print(f"[html_to_obsidian] ⚠ Could not fetch YouTube title: {e}", file=sys.stderr)
    return None


def sanitize_filename(title: str) -> str:
    """Convert a title to a safe filename."""
    # Remove/replace unsafe characters
    safe = re.sub(r'[\\/:*?"<>|]', '-', title)
    # Replace multiple whitespace/spaces with single space
    safe = re.sub(r'\s+', ' ', safe)
    # Trim and limit length
    safe = safe.strip()[:80]
    return safe


def extract_html_sections(html_path: str) -> dict:
    """Parse HTML and extract structured content."""
    with open(html_path, encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    result = {
        "title": "",
        "video_url": "",
        "video_id": "",
        "hero": {},
        "summary": "",
        "sections": [],
    }

    # Title from <title> tag
    title_tag = soup.find("title")
    if title_tag:
        full_title = title_tag.get_text(strip=True)
        result["title"] = full_title.split(" — ")[0] if " — " in full_title else full_title

    # Video URL from the subtitle panel link
    yt_link = soup.find("a", class_="sub-yt")
    if yt_link and yt_link.get("href"):
        result["video_url"] = yt_link["href"]
        m = re.search(r"v=([\w-]+)", result["video_url"])
        if m:
            result["video_id"] = m.group(1)

    # Hero section
    hero = soup.find("div", id="hero")
    if hero:
        hero_div = hero.find("div", class_="hero")
        if hero_div:
            badge = hero_div.find("div", class_="hero-badge")
            h1 = hero_div.find("h1")
            sub = hero_div.find("div", class_="hero-sub")
            quote = hero_div.find("div", class_="hero-quote")
            chips = hero_div.find_all("span", class_="chip")

            result["hero"] = {
                "badge": badge.get_text(strip=True) if badge else "",
                "title": h1.get_text(strip=True) if h1 else "",
                "sub": sub.get_text(strip=True) if sub else "",
                "quote": quote.get_text(strip=True) if quote else "",
                "tags": [c.get_text(strip=True) for c in chips],
            }

    # Summary section
    summary = soup.find("div", id="summary")
    if summary:
        card = summary.find("div", class_="card")
        if card:
            h = html2text.HTML2Text()
            h.body_width = 0
            h.ignore_links = False
            h.ignore_images = True
            h.wrap_links = False
            result["summary"] = h.handle(str(card)).strip()

    # Content sections (s1-sN)
    for sec in soup.find_all("div", class_="sec"):
        sec_id = sec.get("id", "")
        if not re.match(r"^s\d+$", sec_id):
            continue

        hd = sec.find("div", class_="sec-hd")
        section_title = ""
        if hd:
            title_div = hd.find("div", class_="sec-title")
            if title_div:
                section_title = title_div.get_text(strip=True)

        body_parts = []
        for child in sec.children:
            if child == hd:
                continue
            if not child.name:
                continue
            body_parts.append(str(child))

        body_html = "".join(body_parts)
        h = html2text.HTML2Text()
        h.body_width = 0
        h.ignore_links = False
        h.ignore_images = True
        h.wrap_links = False
        h.ignore_emphasis = False
        body_md = h.handle(body_html).strip()
        body_md = re.sub(r"\n{3,}", "\n\n", body_md)

        result["sections"].append({
            "id": sec_id,
            "title": section_title,
            "body": body_md,
        })

    return result


def build_markdown(sections: dict, yt_title: str = "") -> str:
    """Build Obsidian-flavored Markdown from extracted sections.

    Uses yt_title (original YouTube title) as H1 if provided.
    The hero title becomes the subtitle line below.
    """
    lines = []
    hero = sections["hero"]

    # YAML frontmatter
    tags = hero.get("tags", [])
    tag_str = "\n  - ".join(tags)
    lines.append("---")
    lines.append("tags:")
    if tag_str:
        lines.append(f"  - {tag_str}")
    lines.append("type: video-notes")
    if sections["video_url"]:
        lines.append(f"url: {sections['video_url']}")
    lines.append(f"created: {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}")
    if yt_title:
        lines.append(f"original-title: \"{yt_title}\"")
    lines.append("---")
    lines.append("")

    # Title: original YouTube title as H1, with hero title as subtitle
    if yt_title:
        lines.append(f"# {yt_title}")
        lines.append("")
        hero_title = hero.get("title", "")
        if hero_title and hero_title.lower() not in yt_title.lower():
            lines.append(f"> **{hero_title}**")
            lines.append("")
    else:
        title = hero.get("title", "") or sections.get("title", "Video Notes")
        lines.append(f"# {title}")
        lines.append("")

    # Video link
    if sections["video_url"]:
        lines.append(f"> 📺 [原视频]({sections['video_url']})")
        if hero.get("sub"):
            lines.append(f"> {hero['sub']}")
        lines.append("")

    # Hero quote
    if hero.get("quote"):
        quote = hero["quote"].replace('\n', ' ').strip()
        lines.append(f'> 💬 *"{quote}"*')
        lines.append("")

    # Summary
    if sections["summary"]:
        lines.append("## 核心总结")
        lines.append("")
        lines.append(sections["summary"])
        lines.append("")

    # Content sections
    for i, sec in enumerate(sections["sections"], 1):
        lines.append(f"## {sec['title']}")
        lines.append("")
        if sec["body"]:
            lines.append(sec["body"])
        lines.append("")

    # Footer
    lines.append("---")
    lines.append(f"*由 [video-notes](https://github.com/2992638402-art/video-notes) 自动生成*")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Convert video-notes HTML to Obsidian Markdown"
    )
    parser.add_argument("input_html", help="Path to the HTML notes file")
    parser.add_argument("--output", "-o", help="Output Markdown file path")
    parser.add_argument("--title", "-t", help="Original YouTube video title (auto-fetched if omitted)")
    parser.add_argument("--vault", default=DEFAULT_VAULT,
                        help=f"Obsidian vault path")
    parser.add_argument("--subfolder", default=DEFAULT_SUBFOLDER,
                        help=f"Subfolder within vault (default: {DEFAULT_SUBFOLDER})")
    args = parser.parse_args()

    ensure_deps()

    print(f"[html_to_obsidian] Parsing: {args.input_html}", file=sys.stderr)
    data = extract_html_sections(args.input_html)

    # Fetch or use provided YouTube title
    yt_title = args.title
    if not yt_title and data["video_url"]:
        print(f"[html_to_obsidian] Fetching original YouTube title...", file=sys.stderr)
        yt_title = fetch_youtube_title(data["video_url"])

    if yt_title:
        print(f"[html_to_obsidian] YouTube title: {yt_title}", file=sys.stderr)
        # Use YouTube title for filename
        filebase = sanitize_filename(yt_title)
    else:
        # Fallback: use HTML filename
        filebase = os.path.splitext(os.path.basename(args.input_html))[0]
        filebase = re.sub(r'-notes$', '', filebase)

    md = build_markdown(data, yt_title or "")

    # Determine output path
    if args.output:
        out_path = args.output
    else:
        filename = f"{filebase}.md"
        out_dir = os.path.join(args.vault, args.subfolder)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, filename)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"[html_to_obsidian] Saved: {out_path}", file=sys.stderr)
    print(f"[html_to_obsidian] Sections: {len(data['sections'])}", file=sys.stderr)
    print(f"[html_to_obsidian] Tags: {data['hero'].get('tags', [])}", file=sys.stderr)

    print(out_path)


if __name__ == "__main__":
    main()
