"""
Fetches RSS feeds from food science / analytical chemistry journals
and writes news.json for the digital signage display.
Runs via GitHub Actions every 2 hours — no CORS issues.
"""

import feedparser
import json
import os
import re
import time
import urllib.parse
import urllib.request
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
    return (f"https://media.springernature.com/lw926/springer-static/image/"
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
        # Nature Food: abstract follows "doi:DOI " in content:encoded
        raw_html = ""
        if hasattr(entry, "content") and entry.content:
            raw_html = entry.content[0].get("value", "")
        if not raw_html:
            return ""
        raw_text = strip_html(raw_html)
        m = re.search(r"doi:\S+\s+(.*)", raw_text, re.DOTALL)
        if m:
            text = re.sub(r"\s+", " ", m.group(1)).strip()
            return (text[:ABSTRACT_MAX] + "…") if len(text) > ABSTRACT_MAX else text
        return ""
    elif feed_type in ("frontiers", "generic"):
        # Frontiers + generic news feeds: summary field (plain text or light HTML)
        text = re.sub(r"\s+", " ", strip_html(entry.get("summary", ""))).strip()
        if len(text) < 60:
            return ""
        return (text[:ABSTRACT_MAX] + "…") if len(text) > ABSTRACT_MAX else text
    else:
        return ""  # Elsevier: no abstract in RSS


def upgrade_image_url(url: str) -> str:
    """Upgrade known CDN thumbnail URLs to higher-resolution equivalents."""
    if not url:
        return url
    # Phys.org CDN: /csz/news/tmb/ → /csz/news/800/
    url = re.sub(r'(scx\d\.b-cdn\.net/csz/news/)tmb/', r'\g<1>800/', url)
    return url


def fetch_og_image(url: str, timeout: int = 8) -> str:
    """Fetch article page and return og:image URL (high-res editorial image)."""
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read(65536).decode("utf-8", errors="ignore")
        # og:image can appear in either attribute order
        m = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\'](https?://[^"\']+)["\']',
            html, re.I)
        if not m:
            m = re.search(
                r'<meta[^>]+content=["\'](https?://[^"\']+)["\'][^>]+property=["\']og:image["\']',
                html, re.I)
        return upgrade_image_url(m.group(1)) if m else ""
    except Exception:
        return ""


def extract_image(entry) -> str:
    """Return the largest image URL from media:content, enclosure, or media:thumbnail."""
    # media:content — pick the widest image available
    mc = getattr(entry, "media_content", None)
    if mc:
        best_url, best_w = "", 0
        for m in mc:
            url = m.get("url", "")
            if not url or not re.search(r"\.(jpg|jpeg|png|webp)", url, re.I):
                continue
            try:
                w = int(m.get("width", 0))
            except (ValueError, TypeError):
                w = 0
            if w > best_w or (best_url == "" and url):
                best_url, best_w = url, w
        if best_url:
            return upgrade_image_url(best_url)
    # enclosure (some RSS feeds embed full-res images here)
    for enc in getattr(entry, "enclosures", []):
        if enc.get("type", "").startswith("image/"):
            return upgrade_image_url(enc.get("href", ""))
    # media:thumbnail — last resort, explicitly small
    mt = getattr(entry, "media_thumbnail", None)
    if mt:
        return upgrade_image_url(mt[0].get("url", "") if mt else "")
    return ""


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


# ── Lab researchers ────────────────────────────────────────────────────────
LAB_YEARS_BACK = 4   # dynamic window: current_year - LAB_YEARS_BACK

_GS = "https://scholar.googleusercontent.com/citations?view_op=view_photo&user="
RESEARCHERS = [
    {"name": "Iris Zohar",       "s2_id": "38522818",    "photo": _GS + "YVQd-pwAAAAJ"},
    {"name": "Ofir Benjamin",    "s2_id": "72231484",    "photo": _GS + "FsjV0oIAAAAJ"},
    {"name": "Adi Jonas-Levi",   "s2_id": "2311554993",  "photo": _GS + "MbCf9l4AAAAJ"},
    {"name": "Loai Basheer",     "s2_id": "4157421",     "photo": "media/photos/loai_basheer.png"},
    {"name": "Gilad Davidson-Rozenfeld", "s2_id": "1410646763", "photo": _GS + "vh7tqKQAAAAJ"},
    {"name": "Rafi Steckler",    "s2_id": "1403949953",  "photo": _GS + "BOhLTM0AAAAJ"},
    {"name": "Giora Rytwo",      "s2_id": "4960911",     "photo": "media/photos/giora_rytwo.jpg"},
]

_S2_FIELDS = "title,year,venue,authors,abstract,externalIds,citationCount"


def fetch_s2_papers(researcher: dict, cutoff_year: int) -> list:
    """Fetch recent papers from Semantic Scholar for one researcher."""
    url = (f"https://api.semanticscholar.org/graph/v1/author/{researcher['s2_id']}/papers"
           f"?fields={_S2_FIELDS}&limit=50&sort=publicationDate:desc")
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            break
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(12 * (attempt + 1))
                continue
            return []
        except Exception:
            return []
    else:
        return []

    papers = []
    for p in data.get("data", []):
        year = p.get("year")
        if not year or year < cutoff_year:
            continue
        title = (p.get("title") or "").strip()
        if not title:
            continue
        author_names = [a.get("name", "") for a in (p.get("authors") or []) if a.get("name")]
        if len(author_names) > 3:
            authors_str = ", ".join(author_names[:3]) + " et al."
        else:
            authors_str = ", ".join(author_names)
        doi = ((p.get("externalIds") or {}).get("DOI") or "")
        abstract = (p.get("abstract") or "").strip()
        if not abstract:
            continue  # no abstract = no slide, same rule as RSS articles
        if len(abstract) > ABSTRACT_MAX:
            abstract = abstract[:ABSTRACT_MAX] + "…"
        citations = p.get("citationCount") or 0
        papers.append({
            "title":           title,
            "abstract":        abstract,
            "authors":         authors_str,
            "published":       str(year),
            "venue":           (p.get("venue") or "").strip(),
            "feedName":        "Lab Research",
            "citationCount":   citations,
            "recentCitations": 0,
            "s2_paper_id":     p.get("paperId", ""),
            "url":             f"https://doi.org/{doi}" if doi else "",
            "image":           "",
            "screen":          "both",
            "lab_paper":       True,
            "researcher":      {"name": researcher["name"], "photo": researcher["photo"]},
        })
    return papers


def fetch_recent_citations(paper_id: str, days: int = 30) -> int:
    """Count how many papers citing this one were published in the last `days` days."""
    from datetime import timedelta
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    url = (f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}/citations"
           f"?fields=publicationDate&limit=100")
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            break
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(12 * (attempt + 1))
                continue
            return 0
        except Exception:
            return 0
    else:
        return 0
    count = 0
    for item in data.get("data", []):
        pd = (item.get("citingPaper") or {}).get("publicationDate") or ""
        if pd >= cutoff:
            count += 1
    return count


# ── Feed configuration ─────────────────────────────────────────────────────
FEEDS = [
    # ── Left screen — academic journals ───────────────────────────────────
    {"url": "https://www.nature.com/natfood.rss",
     "name": "Nature Food",              "type": "nature",    "screen": "left"},
    {"url": "https://rss.sciencedirect.com/publication/science/03088146",
     "name": "Food Chemistry",           "type": "elsevier",  "screen": "left"},
    {"url": "https://rss.sciencedirect.com/publication/science/09242244",
     "name": "Trends in Food Sci & Tech","type": "elsevier",  "screen": "left"},
    {"url": "https://rss.sciencedirect.com/publication/science/09503293",
     "name": "Food Quality & Preference","type": "elsevier",  "screen": "left"},
    {"url": "https://www.frontiersin.org/journals/analytical-science/rss",
     "name": "Frontiers Anal. Science",  "type": "frontiers", "screen": "left"},
    {"url": "https://www.frontiersin.org/journals/food-science-and-technology/rss",
     "name": "Frontiers Food Science",   "type": "frontiers", "screen": "left"},
    {"url": "https://rss.sciencedirect.com/publication/science/07400020",
     "name": "Food Microbiology",        "type": "elsevier",  "screen": "left"},
    # ── Right screen — science news + applied ─────────────────────────────
    {"url": "https://phys.org/rss-feed/chemistry-news/analytical-chemistry/",
     "name": "Phys.org Analytics",       "type": "generic",   "screen": "right"},
    {"url": "https://www.sciencedaily.com/rss/plants_animals/biotechnology_and_bioengineering.xml",
     "name": "ScienceDaily Biotech",     "type": "generic",   "screen": "right"},
    {"url": "https://www.sciencedaily.com/rss/health_medicine/nutrition.xml",
     "name": "ScienceDaily Nutrition",   "type": "generic",   "screen": "right"},
    {"url": "https://www.sciencedaily.com/rss/plants_animals/food_agriculture.xml",
     "name": "ScienceDaily Food & Agri", "type": "generic",   "screen": "right"},
    {"url": "https://www.frontiersin.org/journals/nutrition/rss",
     "name": "Frontiers Nutrition",      "type": "frontiers", "screen": "right"},
    {"url": "https://www.mdpi.com/rss/journal/nutrients",
     "name": "Nutrients (MDPI)",         "type": "generic",   "screen": "right"},
    {"url": "https://link.springer.com/search.rss?facet-journal-id=394",
     "name": "Eur. J. Nutrition",        "type": "generic",   "screen": "right"},
]

MAX_PER_FEED = 4   # cards shown per feed
ABSTRACT_MAX = 1600 # characters (~15 lines)

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
            if is_nature:
                image = springer_fig1_url(article_url, current_year)
            elif feed_type == "generic":
                image = fetch_og_image(article_url) or extract_image(entry)
            else:
                image = ""

            items.append({
                "title":     title,
                "abstract":  abstract,
                "authors":   authors,
                "published": published,
                "feedName":  feed_info["name"],
                "url":       article_url,
                "image":     image,
                "screen":    feed_info.get("screen", "both"),
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

# ── Lab papers ─────────────────────────────────────────────────────────────
cutoff_year = current_year - LAB_YEARS_BACK
print(f"\nFetching lab papers (>= {cutoff_year})...")
for researcher in RESEARCHERS:
    papers = fetch_s2_papers(researcher, cutoff_year)
    items.extend(papers)
    print(f"  {researcher['name']}: {len(papers)} papers")
    time.sleep(1.5)  # respect S2 rate limit

# ── Recent citations (last 30 days) per lab paper ──────────────────────────
print("\nFetching recent citations...")
for item in items:
    if not item.get("lab_paper"):
        continue
    if not item.get("citationCount", 0):
        continue
    pid = item.get("s2_paper_id", "")
    if not pid:
        continue
    recent = fetch_recent_citations(pid)
    item["recentCitations"] = recent
    if recent:
        print(f"  ▲{recent} recent: {item['title'][:50]}")
    time.sleep(1.0)  # respect S2 rate limit

result = {
    "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "items":   items,
}

with open("news.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"\nDone — news.json: {len(items)} items")
