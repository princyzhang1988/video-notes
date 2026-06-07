#!/usr/bin/env python3
"""Inject subtitle JSON into HTML after LLM has generated the notes.

This is a post-processing step: the LLM generates HTML with the placeholder
"__SUBS_JSON__", and this script replaces it with the actual subtitle JSON.
This way the JSON never enters the LLM context (saving ~7K tokens), but the
final HTML has fully functional subtitle search.
"""

import json
import sys


def inject(html_path, subs_path):
    with open(subs_path) as f:
        subs = json.load(f)

    with open(html_path) as f:
        html = f.read()

    subs_json = json.dumps(subs, ensure_ascii=False)
    placeholder = '__SUBS_JSON__'

    if placeholder not in html:
        print(f"WARNING: placeholder {placeholder} not found in HTML")
        return False

    html = html.replace(placeholder, subs_json)

    with open(html_path, 'w') as f:
        f.write(html)

    size_kb = len(subs_json) / 1024
    print(f"Injected {len(subs)} subtitle segments ({size_kb:.1f}KB) into {html_path}")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <html_file> <subs.json>")
        sys.exit(1)

    inject(sys.argv[1], sys.argv[2])
