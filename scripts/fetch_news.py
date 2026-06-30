"""
Fetches RSS feeds from food science / analytical chemistry journals
and writes news.json for the digital signage display.
Runs via GitHub Actions every 2 hours — no CORS issues.
"""

import feedparser
import json
import os
import re
import urllib.parse
from datetime import datetime, timezone
from html.parser import HTMLParser

BROWSER_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


# ── Springer Nature Fig1 URL ───────────────────────────────────────────────
def springer_fig1_url(article_url: str, year: int) -> str:
    """Construct the Springer CDN URL for Fig1 directly from the article URL.

    Nature URL: .../articles/s{journal}-{yy}-{num}-{check}
    CDN URL:    media.springernature.com/m685/springer-static/image/
                art%3A{encoded_doi}/MediaObjects/{journal}_{year}_{num}_Fig1_HTML.png
    """
    m = re.search(r'nature\.com/articles/(s(\d+)-\d+-0*(\d+)-\d+)', article_url)
    if not m:
        return ""
    suffix  = m.group(1)       # s43016-026-01368-3
    journal = m.group(2)       # 43016
    art_num = int(m.group(3))  # 1368 (leading zeros stripped)
    doi     = f"10.1038/{suffix}"
    enc     = urllib.parse.quote(f"art:{doi}", safe="")
    return (f"https://media.springernature.com/m685/springer-static/image/"
            f"{enc}/MediaObjects/{journal}_{year}_{art_num}_Fig1_HTML.png")


# ── HTML helpers ───────────────────────────────────────────────────────────
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
    return re.sub(r"\s+", " ", s.get_text()).strip()


def get_raw_html(entry) -> str:
    """Return the richest HTML field from an RSS entry."""
    if hasattr(entry, "content") and entry.content:
        return entry.content[0].get("value", "")
    for field in ("summary", "description"):
        v = entry.get(field, "")
        if v:
            return v
    return ""


# ── Field extractors ───────────────────────────────────────────────────────
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def extract_abstract(entry, feed_type: str) -> str:
    """Return article abstract text, or '' if not available."""
    if feed_type == "nature":
        # Nature: abstract follows "doi:DOI " in content:encoded
        raw_html = ""
        if hasattr(entry, "content") and entry.content:
            raw_html = entry.content[0].get("value", "")
        if not raw_html:
            return ""
        raw_text = strip_html(raw_html)
        m = re.search(r"doi:\S+\s+(.*)", raw_text, re.DOTALL)
        if m:
            text = re.sub(r"\s+", " ", m.group(1)).strip()
            return (text[:420] + "…") if len(text) > 420 else text
        return ""
    elif feed_type == "frontiers":
        # Frontiers: abstract is plain text in entry.summary
        text = re.sub(r"\s+", " ", strip_html(entry.get("summary", ""))).strip()
        if len(text) < 80:
            return ""
        return (text[:420] + "…") if len(text) > 420 else text
    else:
        return ""  # Elsevier: no abstract in RSS


def extract_authors(entry, raw_html: str) -> str:
    """Return up to 3 author names."""
    # feedparser fills entry.authors as list of {name, ...}
    if hasattr(entry, "authors") and entry.authors:
        names = [a.get("name", "").strip() for a in entry.authors if a.get("name", "").strip()]
        if names:
            suffix = " et al." if len(names) > 3 else ""
            return ", ".join(names[:3]) + suffix
    # feedparser single entry.author (dc:creator first occurrence)
    if entry.get("author", "").strip():
        return entry["author"].strip()
    # Elsevier description HTML: "Author(s): Name1, Name2"
    m = re.search(r"Author\(s\):\s*(.*?)(?:</p>|<br|\Z)", raw_html, re.I | re.S)
    if m:
        text  = strip_html(m.group(1)).strip()
        parts = [p.strip() for p in text.split(",") if p.strip()]
        suffix = " et al." if len(parts) > 3 else ""
        return ", ".join(parts[:3]) + suffix
    return ""


def extract_date(entry, raw_html: str) -> str:
    """Return date as 'Mon YYYY', e.g. 'Jun 2026'."""
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            return f"{MONTHS[t.tm_mon - 1]} {t.tm_year}"
    # Elsevier HTML: "Publication date: 15 July 2026"
    m = re.search(r"Publication date:\s*(?:\d+\s+)?([A-Za-z]+)\s+(\d{4})", raw_html, re.I)
    if m:
        return f"{m.group(1)[:3].capitalize()} {m.group(2)}"
    return ""


# ── Feed configuration ─────────────────────────────────────────────────────
FEEDS = [
    {"url": "https://www.nature.com/natfood.rss",
     "name": "Nature Food",              "type": "nature"},
    {"url": "https://rss.sciencedirect.com/publication/science/03088146",
     "name": "Food Chemistry",           "type": "elsevier"},
    {"url": "https://rss.sciencedirect.com/publication/science/09242244",
     "name": "Trends in Food Sci & Tech","type": "elsevier"},
    {"url": "https://rss.sciencedirect.com/publication/science/09503293",
     "name": "Food Quality & Preference","type": "elsevier"},
    {"url": "https://www.frontiersin.org/journals/analytical-science/rss",
     "name": "Frontiers Anal. Science",  "type": "frontiers"},
    {"url": "https://www.frontiersin.org/journals/food-science-and-technology/rss",
     "name": "Frontiers Food Science",   "type": "frontiers"},
]

MAX_PER_FEED = 4   # cards shown per feed
ABSTRACT_MAX = 420 # characters

# ── Main loop ─────────────────────────────────────────────────────────────
# Load previous news.json to use as fallback for feeds that fail to fetch
_prev_by_feed: dict = {}
if os.path.exists("news.json"):
    try:
        with open("news.json", encoding="utf-8") as _f:
            _prev = json.load(_f)
        for _it in (_prev.get("items") or []):
            _prev_by_feed.setdefault(_it.get("feedName", ""), []).append(_it)
    except Exception:
        pass

items        = []
current_year = datetime.now(timezone.utc).year

for feed_info in FEEDS:
    feed_type = feed_info.get("type", "generic")
    is_nature = feed_type == "nature"
    try:
        feed  = feedparser.parse(feed_info["url"],
                                 request_headers={"User-Agent": BROWSER_UA})
        count = 0
        for entry in feed.entries:
            if count >= MAX_PER_FEED:
                break
            title = strip_html(entry.get("title") or "").strip()
            if not title:
                continue

            article_url = entry.get("link", "")
            raw_html    = get_raw_html(entry)

            abstract  = extract_abstract(entry, feed_type)
            authors   = extract_authors(entry, raw_html)
            published = extract_date(entry, raw_html)
            image     = springer_fig1_url(article_url, current_year) if is_nature else ""

            items.append({
                "title":     title,
                "abstract":  abstract,
                "authors":   authors,
                "published": published,
                "feedName":  feed_info["name"],
                "url":       article_url,
                "image":     image,
            })
            count += 1

        if count == 0:
            # Feed returned nothing — reuse cached articles from previous run
            cached = _prev_by_feed.get(feed_info["name"], [])[:MAX_PER_FEED]
            items.extend(cached)
            print(f"  {feed_info['name']}: 0 fetched — reused {len(cached)} cached")
        else:
            print(f"  {feed_info['name']}: {count} articles")

    except Exception as e:
        # Network/parse error — reuse cache
        cached = _prev_by_feed.get(feed_info["name"], [])[:MAX_PER_FEED]
        items.extend(cached)
        print(f"  ERROR {feed_info['name']}: {e} — reused {len(cached)} cached")

result = {
    "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "items":   items,
}

with open("news.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"\nDone — news.json: {len(items)} items")
