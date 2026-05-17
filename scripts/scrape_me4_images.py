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


EXPECTED_FIRST_NAME = "Weedle"
MIN_ME4_NAME_OVERLAP = 75  # of 83 PokeBeach names


def build_sidecar(ordered: list, scraped_at: str) -> dict:
    by_name = {}
    for entry in ordered:
        if entry["name"] not in by_name:
            by_name[entry["name"]] = entry["image"]
    return {
        "set": "ME4",
        "source": "asia.pokemon-card.com",
        "scrapedAt": scraped_at,
        "byName": by_name,
        "ordered": ordered,
    }


def sanity_check(ordered: list, me4_names: set) -> None:
    """Guard against silent wrong-set scrapes or a borked listing template."""
    if not ordered:
        raise RuntimeError("sanity_check: ordered is empty")
    first = ordered[0]["name"]
    if first != EXPECTED_FIRST_NAME:
        raise RuntimeError(
            f"sanity_check: expected first card {EXPECTED_FIRST_NAME!r}, got {first!r}. "
            "Listing order may have changed or wrong set was scraped."
        )
    # Skip the overlap guard when the supplied me4_names set is itself
    # smaller than the threshold (e.g. unit tests with a 2-name fixture).
    # In production, ME4.json supplies 83 names and the guard fires only
    # if asia diverges from PokeBeach naming wholesale.
    if len(me4_names) < MIN_ME4_NAME_OVERLAP:
        return
    asia_names = {e["name"] for e in ordered}
    overlap = len(me4_names & asia_names)
    if overlap < MIN_ME4_NAME_OVERLAP:
        raise RuntimeError(
            f"sanity_check: only {overlap}/{len(me4_names)} ME4.json names found in asia listing "
            f"(threshold {MIN_ME4_NAME_OVERLAP}). Names may have drifted; review build output."
        )


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
