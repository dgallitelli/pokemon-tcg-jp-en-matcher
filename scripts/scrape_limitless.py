#!/usr/bin/env python3
"""
Limitless TCG Coverage Checker & Scraper.

Checks EN translation coverage for all known JP sets (M* and SV*).
For M* sets with missing/incomplete EN translations, scrapes full card data
from Limitless TCG and writes data/ME*.json files.
"""

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("ERROR: 'requests' package required. Install with: pip install requests")

try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("ERROR: 'beautifulsoup4' package required. Install with: pip install beautifulsoup4")

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent / "data"

LIMITLESS_BASE = "https://limitlesstcg.com/cards/jp"
TCGDEX_API = "https://api.tcgdex.net/v2"

# Energy cost letter → full type name (Limitless uses single-letter abbreviations)
ENERGY_MAP = {
    "G": "Grass",
    "R": "Fire",
    "W": "Water",
    "L": "Lightning",
    "P": "Psychic",
    "F": "Fighting",
    "D": "Darkness",
    "M": "Metal",
    "C": "Colorless",
    "N": "Dragon",
    "Y": "Fairy",
}

# JP set ID → EN sideload configuration
SET_CONFIG = {
    "M1S": {
        "en_set_id": "ME1",
        "en_set_name": "Mega Evolution",
        "card_count": 92,
        "serie": "Mega Evolution",
        "release_date": "2026-01-23",
    },
    "M1L": {
        "en_set_id": "ME1",
        "en_set_name": "Mega Evolution",
        "card_count": 92,
        "serie": "Mega Evolution",
        "release_date": "2026-01-23",
    },
    "M2": {
        "en_set_id": "ME2",
        "en_set_name": "Phantasmal Flames",
        "card_count": 116,
        "serie": "Mega Evolution",
        "release_date": "2026-02-27",
    },
    "M2a": {
        "en_set_id": "ME2a",
        "en_set_name": "MEGA Dream ex",
        "card_count": 193,
        "serie": "Mega Evolution",
        "release_date": "2026-03-13",
    },
    "M3": {
        "en_set_id": "ME3",
        "en_set_name": "Perfect Order",
        "card_count": 117,
        "serie": "Mega Evolution",
        "release_date": "2026-03-27",
    },
    "M4": {
        "en_set_id": "ME4",
        "en_set_name": "Ninja Spinner",
        "card_count": 120,
        "serie": "Mega Evolution",
        "release_date": "2026-05-22",
    },
}

# SV* set IDs to skip (deck-builder / promo sets, not standard expansions)
SV_SKIP_IDS = {"SVLS", "SVK", "SVLN", "SVP"}


def check_m_coverage(jp_set_id: str, cfg: dict) -> dict:
    """
    Check if the existing ME*.json has real EN content for a given JP set.

    Returns a dict with:
      - "status": "ok" | "missing" | "incomplete"
      - "reason": human-readable explanation
      - "file_path": Path to the EN sideload file
    """
    en_set_id = cfg["en_set_id"]
    file_path = DATA_DIR / f"{en_set_id}.json"

    if not file_path.exists():
        return {"status": "missing", "reason": "EN sideload file does not exist", "file_path": file_path}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        return {"status": "missing", "reason": f"Cannot read file: {e}", "file_path": file_path}

    cards = data.get("cards", {})
    if not cards:
        return {"status": "missing", "reason": "File has no cards", "file_path": file_path}

    # Sample card #1 and midpoint
    card_keys = sorted(cards.keys())
    sample_keys = [card_keys[0]]
    mid = len(card_keys) // 2
    if mid > 0 and mid < len(card_keys):
        sample_keys.append(card_keys[mid])

    for key in sample_keys:
        card = cards[key]
        # Check: has a non-null image OR at least one attack with a non-dash name
        has_image = card.get("image") is not None
        has_real_attack = any(
            a.get("name") and a["name"] != "\u2014"
            for a in card.get("attacks", [])
        )
        has_effect = bool(card.get("effect"))

        if has_image or has_real_attack or has_effect:
            continue
        else:
            return {
                "status": "incomplete",
                "reason": f"Card {key} has no image and no real attack names/effects",
                "file_path": file_path,
            }

    return {"status": "ok", "reason": "Coverage OK", "file_path": file_path}


def check_all_m_sets() -> dict:
    """
    Check coverage for all M* sets. Returns dict of jp_set_id → coverage result.
    """
    print("=== M* Coverage Check ===")
    results = {}
    for jp_set_id, cfg in SET_CONFIG.items():
        result = check_m_coverage(jp_set_id, cfg)
        en_set_id = cfg["en_set_id"]
        status_icon = {"ok": "\u2705", "missing": "\u274c", "incomplete": "\u274c"}[result["status"]]
        print(f"  {jp_set_id:4s} → {en_set_id:4s}: {status_icon} {result['reason']}")
        results[jp_set_id] = result
    print()
    return results


if __name__ == "__main__":
    check_all_m_sets()
