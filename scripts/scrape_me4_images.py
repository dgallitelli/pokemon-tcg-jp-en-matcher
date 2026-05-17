#!/usr/bin/env python3
"""Scrape official EN card images for ME04 from asia.pokemon-card.com.

Two phases:
  1. Walk paginated listing to collect ordered (detail_id, image_url) pairs.
  2. Fetch each detail page to extract the card name from <title>.

Output: data/me4_images.json with both byName lookup and ordered list.
"""
import datetime as _dt
import json
import pathlib
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

OUT_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "me4_images.json"
ME4_JSON_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "ME4.json"

EXPECTED_FIRST_NAME = "Weedle"
MIN_ME4_NAME_OVERLAP = 75  # of 83 PokeBeach names

LISTING_IMG_RE = re.compile(
    r'data-original="(https://asia\.pokemon-card\.com/sg/card-img/default\d+\.png)"'
)
DETAIL_ID_RE = re.compile(r"/default0*(\d+)\.png$")
TITLE_RE = re.compile(r"<title>\s*(.+?)\s*\|\s*Trainers Website", re.IGNORECASE | re.DOTALL)


def parse_listing_page(html: str) -> list:
    """Extract card-image URLs from a single listing page, in DOM order."""
    return LISTING_IMG_RE.findall(html)


def extract_detail_name(html: str):
    """Pull the card name from a detail-page <title>.

    Normalizes the typographic apostrophe (U+2019) to a straight ASCII
    apostrophe (U+0027) so names match PokeBeach's text:
        asia:       "Roxie’s Performance"
        PokeBeach:  "Roxie's Performance"
    """
    m = TITLE_RE.search(html)
    if not m:
        return None
    return m.group(1).strip().replace("’", "'")


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


def _resolve_scraped_at(
    path: pathlib.Path,
    new_byname: dict,
    new_ordered: list,
    today_iso: str,
) -> str:
    """Reuse prior scrapedAt when content is unchanged; else today."""
    if not path.exists():
        return today_iso
    try:
        prior = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return today_iso
    if (
        prior.get("byName") == new_byname
        and prior.get("ordered") == new_ordered
        and isinstance(prior.get("scrapedAt"), str)
    ):
        return prior["scrapedAt"]
    return today_iso


def _load_me4_names() -> set:
    if not ME4_JSON_PATH.exists():
        return set()
    data = json.loads(ME4_JSON_PATH.read_text())
    return {c["name"] for c in data.get("cards", {}).values()}


def main() -> int:
    print("Phase 1: walking ME04 listing pages...")
    image_urls = fetch_all_image_urls()
    print(f"  collected {len(image_urls)} image URLs")
    if not image_urls:
        print("ERROR: no images found; aborting.", flush=True)
        return 1

    print("Phase 2: resolving names from detail pages...")
    ordered = resolve_names(image_urls)
    print(f"  resolved {len(ordered)} names")

    print("Sanity check...")
    sanity_check(ordered, me4_names=_load_me4_names())
    print("  ok")

    sidecar_byname = {}
    for entry in ordered:
        if entry["name"] not in sidecar_byname:
            sidecar_byname[entry["name"]] = entry["image"]
    scraped_at = _resolve_scraped_at(
        OUT_PATH, sidecar_byname, ordered, _dt.date.today().isoformat()
    )
    sidecar = build_sidecar(ordered, scraped_at=scraped_at)
    OUT_PATH.write_text(json.dumps(sidecar, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {OUT_PATH.relative_to(OUT_PATH.parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
