#!/usr/bin/env python3
"""Scrape official EN card images for ME04 from asia.pokemon-card.com.

Two phases:
  1. Walk paginated listing to collect ordered (detail_id, image_url) pairs.
  2. Fetch each detail page to extract the card name from <title>.

Output: data/me4_images.json with both byName lookup and ordered list.
"""
import re

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
