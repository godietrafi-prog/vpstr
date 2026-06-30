"""
Fetches RSS feeds from food science / analytical chemistry journals
and writes news.json for the digital signage display.
Runs via GitHub Actions every 2 hours — no CORS issues.
"""

import feedparser
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser

FEEDS = [
    {"url": "https://www.nature.com/natfood.rss",
     "name": "Nature Food"},
    {"url": "https://rss.sciencedirect.com/publication/science/03088146",
     "name": "Food Chemistry"},
    {"url": "https://rss.sciencedirect.com/publication/science/09242244",
     "name": "Trends in Food Science & Technology"},
    {"url": "https://rss.sciencedirect.com/publication/science/09503293",
     "name": "Food Quality & Preference"},
]

MAX_PER_FEED = 4   # article cards shown in slideshow
SUMMARY_MAX  = 300 # characters for the abstract snippet


class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result = []

    def handle_data(self, d):
        self.result.append(d)

    def get_text(self):
        return " ".join(self.result)


def strip_html(html: str) -> str:
    s = HTMLStripper()
    try:
        s.feed(html or "")
    except Exception:
        return ""
    text = s.get_text()
    return re.sub(r"\s+", " ", text).strip()


def clean_summary(raw: str) -> str:
    """Remove boilerplate RSS metadata, keep meaningful content."""
    raw = raw.strip()

    # Nature: "Nature Food, Published online: DATE; doi:DOI ACTUAL TEXT"
    m = re.search(r'doi:\S+\s+(.*)', raw, re.DOTALL)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()

    # Elsevier: "Publication date: ... Source: ... Author(s): NAMES"
    if raw.startswith("Publication date:"):
        # Extract author names as the useful part
        m2 = re.search(r'Author\(s\):\s*(.+)', raw)
        if m2:
            authors = m2.group(1).strip()
            # Keep only first 3 authors
            parts = [a.strip() for a in authors.split(",") if a.strip()][:3]
            return "Authors: " + ", ".join(parts)
        return ""

    return raw


items = []

for feed_info in FEEDS:
    try:
        feed = feedparser.parse(feed_info["url"])
        count = 0
        for entry in feed.entries:
            if count >= MAX_PER_FEED:
                break
            title = strip_html((entry.get("title") or "")).strip()
            if not title:
                continue

            # Build summary from best available field
            raw_summary = ""
            for field in ("summary", "description", "content"):
                raw = ""
                if field == "content" and hasattr(entry, "content"):
                    raw = entry.content[0].get("value", "") if entry.content else ""
                else:
                    raw = entry.get(field, "")
                if raw:
                    raw_summary = strip_html(raw)
                    break

            summary = clean_summary(raw_summary)
            if len(summary) > SUMMARY_MAX:
                summary = summary[:SUMMARY_MAX - 3] + "..."

            items.append({
                "title":    title,
                "summary":  summary,
                "feedName": feed_info["name"],
                "url":      entry.get("link", ""),
            })
            count += 1

        print(f"  {feed_info['name']}: {count} articles")

    except Exception as e:
        print(f"  ERROR {feed_info['name']}: {e}")

result = {
    "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "items":   items,
}

with open("news.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"\nDone — news.json: {len(items)} items")
