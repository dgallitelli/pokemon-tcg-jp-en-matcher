#!/usr/bin/env python3
"""
Limitless TCG Coverage Checker & Scraper.

Checks EN translation coverage for all known JP sets (M* and SV*).
For M* sets with missing/incomplete EN translations, scrapes full card data
from Limitless TCG and writes data/ME*.json files.
"""

from __future__ import annotations

import argparse
import copy
import json
import random
import re
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
    # M1S and M1L both map to ME1 (unified 1-188 numbering: M1S=1-92, M1L=93-188).
    # ME1 was built by the older pipeline (fetch_tcgdex_en.py + normalize_data.py) and
    # cannot be re-scraped from Limitless without a merge step: M1S has its own 1-92
    # numbering on Limitless, and M1L has its own 1-92 numbering -- these must be merged
    # with a +92 offset applied to M1L before writing ME1.json.
    # DO NOT scrape M1S or M1L individually: it would overwrite ME1 with only 92 cards.
    "M1S": {
        "en_set_id": "ME1",
        "en_set_name": "Mega Evolution",
        "card_count": 92,
        "serie": "Mega Evolution",
        "release_date": "2026-01-23",
        "scrape_disabled": True,  # See note above — ME1 requires merge of M1S+M1L
    },
    "M1L": {
        "en_set_id": "ME1",
        "en_set_name": "Mega Evolution",
        "card_count": 92,
        "serie": "Mega Evolution",
        "release_date": "2026-01-23",
        "scrape_disabled": True,  # See note above — ME1 requires merge of M1S+M1L
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
        "card_count": 83,  # Limitless only indexes 83/120 cards (cards 84-120 return 404)
        "serie": "Mega Evolution",
        "release_date": "2026-05-22",
    },
}

# SV* set IDs to skip (deck-builder / promo sets, not standard expansions)
SV_SKIP_IDS = {"SVLS", "SVK", "SVLN", "SVP"}


###############################################################################
# HTML Parser — fetch and parse individual card pages from Limitless TCG
###############################################################################

# Reverse map: full type name → single letter (for weakness/resistance parsing)
TYPE_NAME_MAP = {v: k for k, v in ENERGY_MAP.items()}
# Also map type names directly for weakness/resistance
TYPE_NAMES = set(ENERGY_MAP.values())


def fetch_card_page(jp_set_id: str, card_num: int) -> str | None:
    """
    Fetch a single card page from Limitless TCG with English translation.

    Returns the HTML string, or None on failure.
    """
    url = f"{LIMITLESS_BASE}/{jp_set_id}/{card_num}?translate=en"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if resp.status_code == 200:
            return resp.text
        print(f"  WARN: HTTP {resp.status_code} for {url}")
        return None
    except requests.RequestException as e:
        print(f"  WARN: Request failed for {url}: {e}")
        return None


def parse_energy_cost(cost_text: str) -> list[str]:
    """
    Convert a Limitless energy letter string (e.g. 'GCC') into a list of
    full type names (e.g. ['Grass', 'Colorless', 'Colorless']).
    """
    result = []
    for ch in cost_text.strip():
        mapped = ENERGY_MAP.get(ch.upper())
        if mapped:
            result.append(mapped)
    return result


def parse_attacks(soup) -> list[dict]:
    """
    Parse all attack divs from the card page.

    Each attack is inside a <div class="card-text-attack"> with:
      - <p class="card-text-attack-info">: energy symbols (span.ptcg-symbol) + name + damage
      - <p class="card-text-attack-effect">: optional effect text
    """
    attacks = []
    for atk_div in soup.select("div.card-text-attack"):
        info_el = atk_div.select_one("p.card-text-attack-info")
        if not info_el:
            continue

        # Extract energy cost from span.ptcg-symbol elements
        cost = []
        for sym_span in info_el.select("span.ptcg-symbol"):
            cost.extend(parse_energy_cost(sym_span.get_text()))

        # Remove the energy spans to get the remaining text (name + damage)
        for sym_span in info_el.select("span.ptcg-symbol"):
            sym_span.decompose()

        remaining = info_el.get_text(strip=True)

        # The remaining text is like "Surprise Attack 30" or "One-Strike Reversal 70+"
        # Split into name and damage. Damage is the last token if it looks numeric.
        parts = remaining.rsplit(None, 1)
        name = remaining
        damage = None
        if len(parts) == 2:
            # Check if last part is a damage value (digits, possibly with +/- suffix)
            dmg_str = parts[1].rstrip("+").rstrip("-")
            if dmg_str.isdigit():
                name = parts[0]
                damage = parts[1]

        # Parse effect text
        effect_el = atk_div.select_one("p.card-text-attack-effect")
        effect = None
        if effect_el:
            effect_text = effect_el.get_text(strip=True)
            if effect_text:
                effect = effect_text

        attack = {"name": name, "cost": cost}
        if damage is not None:
            # Store as string to preserve "70+" format; convert pure numbers to int
            clean = damage.rstrip("+").rstrip("-")
            if clean.isdigit() and damage == clean:
                attack["damage"] = int(damage)
            else:
                attack["damage"] = damage
        if effect:
            attack["effect"] = effect

        attacks.append(attack)

    return attacks


def parse_abilities(soup) -> list[dict]:
    """
    Parse all ability divs from the card page.

    Each ability is inside a <div class="card-text-ability"> with:
      - <p class="card-text-ability-info">: "Ability: Name"
      - <p class="card-text-ability-effect">: effect text
    """
    abilities = []
    for abl_div in soup.select("div.card-text-ability"):
        info_el = abl_div.select_one("p.card-text-ability-info")
        effect_el = abl_div.select_one("p.card-text-ability-effect")

        if not info_el:
            continue

        # Text is like "Ability:  Night Raid"
        info_text = info_el.get_text(strip=True)
        name = info_text
        if ":" in info_text:
            name = info_text.split(":", 1)[1].strip()

        ability = {"type": "Ability", "name": name}
        if effect_el:
            effect_text = effect_el.get_text(strip=True)
            if effect_text:
                ability["effect"] = effect_text

        abilities.append(ability)

    return abilities


def _parse_wrr_text(soup) -> str:
    """
    Extract the raw text from the weakness/resistance/retreat section.

    Located in <p class="card-text-wrr">.
    """
    wrr_el = soup.select_one("p.card-text-wrr")
    if wrr_el:
        return wrr_el.get_text()
    return ""


def parse_weakness(wrr_text: str) -> dict | None:
    """
    Parse weakness from the WRR text block.

    Format: "Weakness: Fire" (value is always x2 in modern TCG).
    """
    for line in wrr_text.split("\n"):
        line = line.strip()
        if line.lower().startswith("weakness:"):
            wtype = line.split(":", 1)[1].strip()
            if wtype.lower() == "none" or not wtype:
                return None
            return {"type": wtype, "value": "x2"}
    return None


def parse_resistance(wrr_text: str) -> dict | None:
    """
    Parse resistance from the WRR text block.

    Format: "Resistance: Fighting" (value is always -30 in modern TCG).
    """
    for line in wrr_text.split("\n"):
        line = line.strip()
        if line.lower().startswith("resistance:"):
            rtype = line.split(":", 1)[1].strip()
            if rtype.lower() == "none" or not rtype:
                return None
            return {"type": rtype, "value": "-30"}
    return None


def parse_retreat(wrr_text: str) -> int:
    """
    Parse retreat cost from the WRR text block.

    Format: "Retreat: 2"
    """
    for line in wrr_text.split("\n"):
        line = line.strip()
        if line.lower().startswith("retreat:"):
            val = line.split(":", 1)[1].strip()
            try:
                return int(val)
            except ValueError:
                return 0
    return 0


def _clean_effect_html(section) -> str:
    """
    Convert a card-text section element to clean effect text.

    Handles <br> → newline, energy symbol spans (ptcg-font with [copy-only]
    brackets), and collapses whitespace.
    """
    section = copy.copy(section)

    # Remove copy-only bracket spans: <span class="copy-only">[</span>
    for span in section.select("span.copy-only"):
        span.decompose()

    # Replace energy symbol spans with readable text:
    # <span style="font-family: ptcg-font" data-tooltip="Fire">R</span> → [R]
    for span in section.select("span[data-tooltip]"):
        letter = span.get_text(strip=True)
        full_name = ENERGY_MAP.get(letter.upper(), letter)
        span.replace_with(f" {full_name} ")

    # Replace reminder-text spans to preserve parentheses
    for span in section.select("span.reminder-text"):
        text = span.get_text(strip=True)
        span.replace_with(f" {text}")

    # Replace <br> with newline markers
    for br in section.find_all("br"):
        br.replace_with("\n")

    raw = section.get_text()
    # Collapse whitespace within each line, then rejoin non-empty lines
    lines = []
    for line in raw.split("\n"):
        stripped = " ".join(line.split())
        if stripped:
            lines.append(stripped)

    return "\n".join(lines)


def parse_effect_text(soup) -> str | None:
    """
    Parse the effect text for Trainer/Energy cards.

    For non-Pokemon cards, the effect text is a direct text node inside the
    second <div class="card-text-section"> (the one after the title/type section).
    It has no wrapper div — just raw text with <br> tags.
    """
    sections = soup.select("div.card-text-section")
    if len(sections) < 2:
        return None

    # The second section contains the effect text for Trainer/Energy.
    # For Pokemon cards this section holds attacks/abilities, so callers
    # should only use this for non-Pokemon cards.
    section = sections[1]

    # If it contains attack or ability divs, it's not a simple effect section
    if section.select("div.card-text-attack") or section.select("div.card-text-ability"):
        return None

    text = _clean_effect_html(section)
    return text if text else None


def parse_card_page(html: str, jp_set_id: str, card_num: int, cfg: dict) -> dict | None:
    """
    Parse a Limitless TCG card page into a card dict matching the ME* schema.

    Returns None if the page cannot be parsed.
    """
    soup = BeautifulSoup(html, "html.parser")

    # --- Card name ---
    name_el = soup.select_one("span.card-text-name a")
    if not name_el:
        print(f"  WARN: No card name found for {jp_set_id}/{card_num}")
        return None
    name = name_el.get_text(strip=True)

    # --- Card image ---
    img_el = soup.select_one("div.card-image img.card")
    image = img_el["src"] if img_el and img_el.get("src") else None

    # --- Category and subcategory from card-text-type ---
    type_el = soup.select_one("p.card-text-type")
    type_text = type_el.get_text(strip=True) if type_el else ""
    # Examples: "Pokémon - Basic", "Pokémon - Stage 2 - Evolves from Golbat",
    #           "Trainer - Item", "Trainer - Supporter", "Energy - Special Energy"
    type_parts = [p.strip() for p in type_text.split("-")]

    # Determine category
    raw_category = type_parts[0] if type_parts else ""
    if "mon" in raw_category.lower():
        category = "Pokemon"
    elif "trainer" in raw_category.lower():
        category = "Trainer"
    elif "energy" in raw_category.lower():
        category = "Energy"
    else:
        category = raw_category

    # --- EN set ID and card ID ---
    en_set_id = cfg["en_set_id"]
    en_set_name = cfg["en_set_name"]
    card_id = f"{en_set_id}-{card_num:03d}"

    if not name:
        print(f"    WARN: Empty card name for {en_set_id}/{card_num:03d} — check Limitless page manually")

    # Guard: warn if any extracted text contains Japanese characters (untranslated content)
    _jp_re = re.compile(r'[\u3040-\u9fff]')
    def _has_jp(text: str) -> bool:
        return bool(text and _jp_re.search(text))
    if _has_jp(name):
        print(f"    WARN: JP text in card name for {en_set_id}/{card_num:03d}: {name!r}")

    # --- Build base card dict ---
    card = {
        "name": name,
        "id": card_id,
        "set": {"id": en_set_id, "name": en_set_name},
        "image": image,
        "category": category,
    }

    # --- Rarity ---
    # Found in: div.card-prints-current span (second span, text like "#1 · Common")
    prints_detail = soup.select_one("div.card-prints-current .prints-current-details")
    rarity = None
    if prints_detail:
        spans = prints_detail.select("span")
        if len(spans) >= 2:
            detail_text = spans[1].get_text(strip=True)
            # Format: "#1 · Common" or just "#1"
            if "·" in detail_text:
                rarity = detail_text.split("·", 1)[1].strip()
    if rarity:
        card["rarity"] = rarity

    # --- Illustrator ---
    artist_el = soup.select_one("div.card-text-artist a")
    if artist_el:
        card["illustrator"] = artist_el.get_text(strip=True)

    if category == "Pokemon":
        # --- HP ---
        title_el = soup.select_one("p.card-text-title")
        if title_el:
            title_text = title_el.get_text()
            # Extract HP: look for pattern like "- 50 HP"
            hp_match = re.search(r"(\d+)\s*HP", title_text)
            if hp_match:
                card["hp"] = int(hp_match.group(1))

            # Extract type from title: "- Grass - 50 HP"
            # The type name is between the card name and the HP
            type_match = re.search(r"-\s*(\w[\w\s]*?)\s*-\s*\d+\s*HP", title_text)
            if type_match:
                pokemon_type = type_match.group(1).strip()
                if pokemon_type in TYPE_NAMES:
                    card["types"] = [pokemon_type]

        # --- Stage ---
        if len(type_parts) >= 2:
            stage_text = type_parts[1].strip()
            # Handle "Stage 2", "Stage 1", "Basic", "MEGA" etc.
            # Also might contain "Evolves from ..." as part of the text
            stage_clean = stage_text.split("Evolves")[0].strip()
            if stage_clean:
                card["stage"] = stage_clean

        # --- Weakness/Resistance/Retreat ---
        wrr_text = _parse_wrr_text(soup)
        weakness = parse_weakness(wrr_text)
        resistance = parse_resistance(wrr_text)
        retreat = parse_retreat(wrr_text)

        if weakness:
            card["weakness"] = weakness
        if resistance:
            card["resistance"] = resistance
        card["retreat"] = retreat

        # --- dexId (empty for now; populated by downstream scripts) ---
        card["dexId"] = []

        # --- Abilities ---
        abilities = parse_abilities(soup)
        if abilities:
            card["abilities"] = abilities

        # --- Attacks ---
        attacks = parse_attacks(soup)
        if attacks:
            card["attacks"] = attacks

    else:
        # Trainer or Energy card
        # --- Subcategory ---
        if len(type_parts) >= 2:
            subcategory = type_parts[1].strip()
            card["subcategory"] = subcategory

        # --- Effect text ---
        effect = parse_effect_text(soup)
        if effect:
            if _has_jp(effect):
                print(f"    WARN: JP text in effect for {en_set_id}/{card_num:03d} — skipping effect field")
            else:
                card["effect"] = effect

    # Final JP text check on attack names/effects
    for atk in card.get("attacks", []):
        if _has_jp(atk.get("name", "")) or _has_jp(atk.get("effect", "")):
            print(f"    WARN: JP text in attack data for {en_set_id}/{card_num:03d}: {atk}")

    return card


###############################################################################
# Full set scraper — fetch all cards, build ME*.json
###############################################################################

def scrape_set(jp_set_id: str, cfg: dict) -> dict:
    """
    Scrape all cards for a JP set from Limitless TCG.
    Returns the complete ME*.json data structure.
    """
    en_set_id = cfg["en_set_id"]
    en_set_name = cfg["en_set_name"]
    card_count = cfg["card_count"]

    print(f"  Scraping {card_count} cards from Limitless ({jp_set_id} -> {en_set_id})...")
    cards = {}
    failures = []

    for num in range(1, card_count + 1):
        num_str = f"{num:03d}"
        html = fetch_card_page(jp_set_id, num)
        if html:
            card = parse_card_page(html, jp_set_id, num, cfg)
            if card:
                cards[num_str] = card
                print(f"    [{num:3d}/{card_count}] {card['name']} ({card.get('category', '?')}) ✓")
            else:
                failures.append(num)
                print(f"    [{num:3d}/{card_count}] Parse FAILED")
        else:
            failures.append(num)
            print(f"    [{num:3d}/{card_count}] Fetch FAILED")

        if num < card_count:
            time.sleep(1)

    if failures:
        print(f"  WARNING: {len(failures)} cards failed: {failures}")

    return {
        "id": en_set_id,
        "name": en_set_name,
        "serie": cfg["serie"],
        "releaseDate": {"en": cfg["release_date"]},
        "jpSetId": jp_set_id,
        "cards": cards,
    }


def preserve_dex_ids(new_data: dict, file_path: Path) -> dict:
    """
    If the EN sideload file already exists, preserve any dexId values
    from existing cards into the new scraped data.
    """
    if not file_path.exists():
        return new_data

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
    except (json.JSONDecodeError, IOError):
        return new_data

    existing_cards = existing.get("cards", {})
    for num_str, card in new_data.get("cards", {}).items():
        if num_str in existing_cards:
            old_card = existing_cards[num_str]
            if old_card.get("dexId") and not card.get("dexId"):
                card["dexId"] = old_card["dexId"]
            elif old_card.get("dexId") and card.get("dexId") == []:
                card["dexId"] = old_card["dexId"]

    return new_data


def write_sideload(data: dict, cfg: dict, strip_images: bool = True):
    """Write the scraped data to data/ME*.json, preserving existing dexIds.

    strip_images: if True (default), set all image fields to null.
    Limitless only hosts JP card scans for these sets, so images must not
    appear in the EN panel (invariant: never show JP image in EN panel).
    """
    en_set_id = cfg["en_set_id"]
    file_path = DATA_DIR / f"{en_set_id}.json"

    data = preserve_dex_ids(data, file_path)

    if strip_images:
        for card in data.get("cards", {}).values():
            card["image"] = None

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    card_count = len(data.get("cards", {}))
    print(f"  Done. Wrote {card_count} cards to {file_path}")


def scrape_missing_m_sets(coverage: dict, only_sets=None, strip_images: bool = True):
    """
    Scrape M* sets that have missing or incomplete EN coverage.
    M1S and M1L both map to ME1 — only scrape once.
    """
    if only_sets:
        unknown = [s for s in only_sets if s not in SET_CONFIG]
        if unknown:
            print(f"  WARNING: Unknown set ID(s): {', '.join(unknown)} — valid: {', '.join(SET_CONFIG.keys())}")

    scraped_en_sets = set()

    for jp_set_id, result in coverage.items():
        cfg = SET_CONFIG[jp_set_id]
        en_set_id = cfg["en_set_id"]

        if only_sets and jp_set_id not in only_sets:
            continue

        if en_set_id in scraped_en_sets:
            print(f"  {jp_set_id} -> {en_set_id}: Already scraped (from prior JP set)")
            continue

        if cfg.get("scrape_disabled"):
            if only_sets and jp_set_id in only_sets:
                print(f"  {jp_set_id} -> {en_set_id}: ⛔ Scraping disabled — {cfg.get('scrape_disabled_reason', 'see SET_CONFIG comment')}")
            continue

        if result["status"] in ("missing", "incomplete"):
            data = scrape_set(jp_set_id, cfg)
            write_sideload(data, cfg, strip_images=strip_images)
            scraped_en_sets.add(en_set_id)
        elif only_sets and jp_set_id in only_sets:
            print(f"  {jp_set_id} -> {en_set_id}: Coverage OK but --sets forces rescrape")
            data = scrape_set(jp_set_id, cfg)
            write_sideload(data, cfg, strip_images=strip_images)
            scraped_en_sets.add(en_set_id)


###############################################################################
# Coverage checker
###############################################################################

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


def check_sv_coverage():
    """
    Check SV* set coverage via TCGdex API.
    For each SV set, pick a random card and check if an EN match exists.
    """
    print("=== SV* Coverage Check ===")

    try:
        resp = requests.get(f"{TCGDEX_API}/ja/sets", timeout=15)
        resp.raise_for_status()
        all_sets = resp.json()
    except requests.RequestException as e:
        print(f"  ERROR fetching JP sets from TCGdex: {e}")
        return

    # Deduplicate by uppercased set ID (TCGdex returns duplicate lowercase entries e.g. sv1a x8)
    sv_sets_dedup = {}
    for s in all_sets:
        sid_upper = s.get("id", "").upper()
        if sid_upper.startswith("SV") and sid_upper not in SV_SKIP_IDS:
            if sid_upper not in sv_sets_dedup:
                sv_sets_dedup[sid_upper] = s
    sv_sets = list(sv_sets_dedup.values())

    if not sv_sets:
        print("  No SV* sets found in TCGdex.")
        return

    print(f"  Found {len(sv_sets)} SV* sets to check.\n")

    for s in sorted(sv_sets, key=lambda x: x.get("id", "").upper()):
        set_id = s.get("id", "")
        set_name = s.get("name", "?")

        try:
            resp = requests.get(f"{TCGDEX_API}/ja/sets/{set_id}", timeout=15)
            resp.raise_for_status()
            set_data = resp.json()
            cards = set_data.get("cards", [])

            if not cards:
                print(f"  {set_id:8s} ({set_name:30s}): ❓ No cards in set")
                time.sleep(0.5)
                continue

            # Prefer Pokemon cards (more likely to have dexId for reliable EN matching)
            pokemon_cards = [c for c in cards if c.get("category") == "Pokemon"] or cards
            sample = random.choice(pokemon_cards)
            card_id = sample.get("id", "")

            resp = requests.get(f"{TCGDEX_API}/ja/cards/{card_id}", timeout=15)
            resp.raise_for_status()
            card_data = resp.json()
            dex_ids = card_data.get("dexId", [])
            card_name = card_data.get("name", "?")

            if dex_ids:
                resp = requests.get(
                    f"{TCGDEX_API}/en/cards",
                    params={"dexId": dex_ids[0]},
                    timeout=15,
                )
                resp.raise_for_status()
                en_cards = resp.json()
                if en_cards:
                    en_name = en_cards[0].get("name", "?")
                    print(f"  {set_id:8s} ({set_name:30s}): ✅ EN match found ({en_name})")
                else:
                    print(f"  {set_id:8s} ({set_name:30s}): ❌ No EN match (dexId={dex_ids[0]}, JP={card_name})")
            else:
                # No dexId — try name-based lookup
                resp = requests.get(
                    f"{TCGDEX_API}/en/cards",
                    params={"name": card_name},
                    timeout=15,
                )
                resp.raise_for_status()
                en_cards = resp.json()
                if en_cards:
                    print(f"  {set_id:8s} ({set_name:30s}): ✅ EN match found (name: {card_name})")
                else:
                    print(f"  {set_id:8s} ({set_name:30s}): ❓ No dexId, name match inconclusive ({card_name})")

        except requests.RequestException as e:
            print(f"  {set_id:8s} ({set_name:30s}): ERROR {e}")

        time.sleep(0.5)

    print()


###############################################################################
# Test helper
###############################################################################

def test_single_card():
    """Test fetching and parsing a single card (M4/1 = Weedle)."""
    jp_set = "M4"
    card_num = 1
    cfg = SET_CONFIG[jp_set]
    print(f"Testing: {jp_set}/{card_num}")
    html = fetch_card_page(jp_set, card_num)
    if not html:
        print("  FAILED to fetch page")
        return
    card = parse_card_page(html, jp_set, card_num, cfg)
    if card:
        print(json.dumps(card, indent=2, ensure_ascii=False))
    else:
        print("  FAILED to parse card")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Limitless TCG Coverage Checker & Scraper",
        epilog=(
            "Examples:\n"
            "  python scrape_limitless.py                  # Check all + scrape missing M* + check SV*\n"
            "  python scrape_limitless.py --check-only     # Coverage report only\n"
            "  python scrape_limitless.py --sets M4,M2a    # Scrape specific sets\n"
            "  python scrape_limitless.py --test-card      # Test single card parse\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--test-card", action="store_true",
                        help="Test parsing a single card (M4/1) and print result")
    parser.add_argument("--check-only", action="store_true",
                        help="Only check coverage (M* + SV*), don't scrape anything")
    parser.add_argument("--sets", type=str, default=None,
                        help="Comma-separated JP set IDs to scrape (e.g. M4,M2a). "
                             "Forces scrape even if coverage is OK.")
    parser.add_argument("--skip-sv", action="store_true",
                        help="Skip SV* coverage check (faster)")
    parser.add_argument("--keep-images", action="store_true",
                        help="Keep image URLs in scraped data (default: strip to null, "
                             "since Limitless only has JP scans which must not show in EN panel)")
    args = parser.parse_args()

    if args.test_card:
        test_single_card()
        sys.exit(0)

    # 1. Check all M* sets
    coverage = check_all_m_sets()

    # 2. Scrape missing M* sets (unless --check-only)
    if not args.check_only:
        only_sets = [s.strip() for s in args.sets.split(",")] if args.sets else None
        strip_images = not args.keep_images
        scrape_missing_m_sets(coverage, only_sets, strip_images=strip_images)

    # 3. Check SV* coverage
    if not args.skip_sv:
        check_sv_coverage()

    print("Done.")
