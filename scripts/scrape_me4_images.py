#!/usr/bin/env python3
"""Scrape official EN card images for ME04 from asia.pokemon-card.com.

Two phases:
  1. Walk paginated listing to collect ordered (detail_id, image_url) pairs.
  2. Fetch each detail page to extract the card name from <title>.

Output: data/me4_images.json with both byName lookup and ordered list.
"""
import re
import time
import urllib.error
import urllib.request

LISTING_URL = (
    "https://asia.pokemon-card.com/sg/card-search/list/"
    "?pageNo={page}&expansionCodes=ME04"
)
DETAIL_URL = "https://asia.pokemon-card.com/sg/card-search/detail/{id}/"
USER_AGENT = "Mozilla/5.0 (compatible; pokemon-tcg-jp-en-matcher/1.0)"
MAX_PAGES = 20  # safety cap; the set has 7 pages

LISTING_IMG_RE = re.compile(
    r'data-original="(https://asia\.pokemon-card\.com/sg/card-img/default\d+\.png)"'
)
DETAIL_ID_RE = re.compile(r"/default0*(\d+)\.png$")
TITLE_RE = re.compile(r"<title>\s*(.+?)\s*\|\s*Trainers Website", re.IGNORECASE | re.DOTALL)


def parse_listing_page(html: str) -> list:
    """Extract card-image URLs from a single listing page, in DOM order."""
    return LISTING_IMG_RE.findall(html)


def extract_detail_name(html: str):
    """Pull the card name from a detail-page <title>."""
    m = TITLE_RE.search(html)
    return m.group(1).strip() if m else None


def _detail_id_from_image_url(url: str) -> int:
    m = DETAIL_ID_RE.search(url)
    if not m:
        raise ValueError(f"Cannot parse detail ID from {url!r}")
    return int(m.group(1))


def _fetch(url: str, timeout: int = 15) -> str:
    """GET a URL with one retry on transient errors."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_err = None
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last_err = e
            if attempt == 1:
                time.sleep(2.0)
                continue
            raise
    assert last_err is not None  # unreachable
    raise last_err


def fetch_all_image_urls(sleep_seconds: float = 0.4) -> list:
    """Walk paginated listing until a page returns zero card images."""
    collected = []
    for page in range(1, MAX_PAGES + 1):
        html = _fetch(LISTING_URL.format(page=page))
        urls = parse_listing_page(html)
        if not urls:
            break
        collected.extend(urls)
        if sleep_seconds:
            time.sleep(sleep_seconds)
    return collected


def resolve_names(image_urls: list, sleep_seconds: float = 0.4) -> list:
    """Fetch each detail page and pair its name with the image URL.

    Returns a list of {"name": str, "image": str}, one per input URL,
    preserving order. Raises RuntimeError if a detail page yields no
    title — that means the asia template changed or the URL is wrong,
    and silently dropping cards would corrupt downstream lookups.
    """
    ordered = []
    for img_url in image_urls:
        detail_id = _detail_id_from_image_url(img_url)
        html = _fetch(DETAIL_URL.format(id=detail_id))
        name = extract_detail_name(html)
        if not name:
            raise RuntimeError(
                f"Detail page {detail_id} has no <title>; cannot resolve card name. "
                f"asia.pokemon-card.com template may have changed."
            )
        ordered.append({"name": name, "image": img_url})
        if sleep_seconds:
            time.sleep(sleep_seconds)
    return ordered
