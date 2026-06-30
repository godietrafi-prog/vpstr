"""
Fetches RSS feeds from food science / analytical chemistry journals
and writes news.json for the digital signage display.
Runs via GitHub Actions every 2 hours — no CORS issues.
"""

import feedparser
import json
import re
import urllib.request
import http.cookiejar
from datetime import datetime, timezone
from html.parser import HTMLParser


# ── og:image fetching ──────────────────────────────────────────────────────
def make_nature_opener():
    """Cookie-jar opener for nature.com (bypasses their cookie wall)."""
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = [
        ("User-Agent",
         "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
        ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
        ("Accept-Language", "en-US,en;q=0.9"),
    ]
    try:
        opener.open("https://www.nature.com/", timeout=8)
    except Exception:
        pass
    return opener


def fetch_og_image(url: str, opener=None) -> str:
    """Return the og:image URL for an article page, or '' on failure."""
    if not url:
        return ""
    try:
        if opener:
            with opener.open(url, timeout=12) as r:
                html = r.read(200000).decode("utf-8", errors="ignore")
        else:
            req = urllib.request.Request(
                url, headers={"User-Agent":
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"})
            with urllib.request.urlopen(req, timeout=12) as r:
                html = r.read(200000).decode("utf-8", errors="ignore")

        for pat in [
            r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)',
            r'content=["\']([^"\']+)["\'][^>]*property=["\']og:image',
            r'name=["\']twitter:image["\'][^>]*content=["\']([^"\']+)',
            r'content=["\']([^"\']+)["\'][^>]*name=["\']twitter:image',
        ]:
            m = re.search(pat, html, re.I)
            if m:
                img = m.group(1).strip()
                # Skip generic journal logos/icons
                if any(x in img for x in ["logo", "icon", "favicon", "rss.png", "header-"]):
                    continue
                return img
    except Exception as e:
        print(f"    og:image error ({url[:60]}): {e}")
    return ""

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

# Prime Nature cookie opener once
nature_opener = make_nature_opener()

for feed_info in FEEDS:
    is_nature = "nature.com" in feed_info["url"]
    try:
        feed = feedparser.parse(feed_info["url"])
        count = 0
        for entry in feed.entries:
            if count >= MAX_PER_FEED:
                break
            title = strip_html((entry.get("title") or "")).strip()
            if not title:
                continue

            article_url = entry.get("link", "")

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

            # Fetch og:image (Nature only — Elsevier returns 403)
            image = ""
            if is_nature and article_url:
                image = fetch_og_image(article_url, opener=nature_opener)
                print(f"    image: {'OK' if image else 'none'} — {title[:50]}")

            items.append({
                "title":    title,
                "summary":  summary,
                "feedName": feed_info["name"],
                "url":      article_url,
                "image":    image,
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
