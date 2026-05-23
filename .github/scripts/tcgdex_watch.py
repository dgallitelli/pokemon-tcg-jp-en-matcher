#!/usr/bin/env python3
"""Open a tracking issue for each TCGdex cards-database release we haven't seen.

Triggered by .github/workflows/tcgdex-watch.yml. Idempotent: matches existing
issues by tag (e.g. "v2.45.0") in the title and skips if found, regardless of
issue state.
"""
from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET

FEED_URL = "https://github.com/tcgdex/cards-database/releases.atom"
ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}
LABEL = "tcgdex-update"
TITLE_PREFIX = "TCGdex update:"

# Patterns scanned against each release body to flag likely-relevant changes.
# Keep in sync with SEREBII_SLUGS / JP_TO_EN_SIDELOAD in app.js and the
# triage checklist in AGENTS.md.
#
# Heuristics intentionally excluded (verified against issues #16-#19, all no-op):
#   - `evolveFrom` — not rendered by the app, so backfills are irrelevant.
#   - generic "trainer/supporter/stadium" — those words appear in nearly every
#     release (every set has trainer cards), drowning the signal.
RELEVANCE = [
    ("JP/EN sideload set (M* / ME*)",
     r"\b(?:m1s|m1l|m2|m2a|m3|m4|m5|me1|me01|me2|me02|me2a|me3|me03|me4|me04|me5|me05|mep)\b"),
    ("SV10 / SV11 (sideloads pull from these)",
     r"\b(?:sv10|sv11w|sv11b)\b"),
    ("Set name in our pipeline",
     r"Mega Evolution|Phantasmal Flames|Perfect Order|Ninja Spinner|"
     r"Destined Rivals|Black Bolt|White Flare"),
    ("dexId field (affects ex-name matching)",
     r"\bdexId\b|Pok[eé]dex ID"),
]

TRIAGE_CHECKLIST = """\
**Triage checklist** (from `AGENTS.md`):
- [ ] Does it add a JP set we sideload (or could now stop sideloading)? \
→ Update `SIDELOAD_JP_CONFIG` / `JP_TO_EN_SIDELOAD` / `LIMITLESS_SET_MAP` in `app.js`.
- [ ] Does it backfill `dexId`s for cards we currently match by name only? \
→ Re-run `fetch_tcgdex_en.py` and `normalize_data.py`; add a regression test.
- [ ] Does it touch a set we already pin (e.g. ME2a / sv10)? \
→ Re-run `generate_tcgdex_m2a.py` so pre-baked image URLs and attack text stay in sync.
"""


def fetch_feed() -> bytes:
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "tcgdex-watch"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def parse_entries(xml_bytes: bytes):
    root = ET.fromstring(xml_bytes)
    out = []
    for e in root.findall("a:entry", ATOM_NS):
        title = (e.findtext("a:title", default="", namespaces=ATOM_NS) or "").strip()
        updated = (e.findtext("a:updated", default="", namespaces=ATOM_NS) or "").strip()
        link_el = e.find("a:link", ATOM_NS)
        link = link_el.get("href") if link_el is not None else ""
        content = e.findtext("a:content", default="", namespaces=ATOM_NS) or ""
        m = re.match(r"(v\d+\.\d+\.\d+)", title)
        tag = m.group(1) if m else None
        if tag:
            out.append({"tag": tag, "title": title, "updated": updated, "link": link, "content_html": content})
    return out


def html_to_markdown(s: str) -> str:
    s = html.unescape(s)
    s = re.sub(r'<a[^>]*href="([^"]+)"[^>]*>([^<]*)</a>', r"[\2](\1)", s)
    s = re.sub(r"<li[^>]*>", "\n- ", s)
    s = re.sub(r"</li>", "", s)
    s = re.sub(r"<h2[^>]*>", "\n## ", s)
    s = re.sub(r"</h2>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s


def find_relevance(body: str) -> list[str]:
    hits = []
    for label, pattern in RELEVANCE:
        if re.search(pattern, body, flags=re.IGNORECASE):
            hits.append(label)
    return hits


def existing_tags() -> set[str]:
    """Return the set of release tags already tracked, by scanning issue titles."""
    result = subprocess.run(
        ["gh", "issue", "list", "--state", "all", "--limit", "200",
         "--search", f"in:title {TITLE_PREFIX}",
         "--json", "title,number"],
        capture_output=True, text=True, check=True,
    )
    issues = json.loads(result.stdout or "[]")
    tags = set()
    for it in issues:
        m = re.search(r"v\d+\.\d+\.\d+", it.get("title", ""))
        if m:
            tags.add(m.group(0))
    return tags


def render_body(entry: dict, hits: list[str]) -> str:
    notes_md = html_to_markdown(entry["content_html"])
    if hits:
        relevance_block = "\n".join(f"- {h}" for h in hits)
    else:
        relevance_block = "_No keywords from our watch list matched. Probably safe to close after a glance._"
    return (
        f"**Tag:** `{entry['tag']}`\n"
        f"**Date:** {entry['updated']}\n"
        f"**Source:** {entry['link']}\n\n"
        f"## Likely relevant to this repo\n{relevance_block}\n\n"
        f"{TRIAGE_CHECKLIST}\n"
        f"---\n\n"
        f"## Upstream release notes\n\n{notes_md}\n\n"
        f"---\n"
        f"_Auto-filed by `.github/workflows/tcgdex-watch.yml`. "
        f"Idempotent per tag — closing this issue won't cause it to reopen._"
    )


def create_issue(entry: dict, body: str) -> None:
    title = f"{TITLE_PREFIX} {entry['tag']} — {entry['title'][len(entry['tag']) + 1:].lstrip(':').strip() or '(no title)'}"
    title = title[:240]
    proc = subprocess.run(
        ["gh", "issue", "create",
         "--title", title,
         "--label", LABEL,
         "--body-file", "-"],
        input=body, text=True, capture_output=True, check=False,
    )
    if proc.returncode != 0:
        print(f"::error::Failed to create issue for {entry['tag']}: {proc.stderr}", file=sys.stderr)
        sys.exit(1)
    print(f"Opened issue for {entry['tag']}: {proc.stdout.strip()}")


def main() -> int:
    entries = parse_entries(fetch_feed())
    if not entries:
        print("Feed returned no entries; nothing to do.")
        return 0
    seen = existing_tags()
    new = [e for e in entries if e["tag"] not in seen]
    print(f"Feed has {len(entries)} entries; {len(seen)} already tracked; {len(new)} new.")
    for entry in new:
        hits = find_relevance(html_to_markdown(entry["content_html"]))
        body = render_body(entry, hits)
        create_issue(entry, body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
