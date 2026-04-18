# Limitless TCG Coverage Checker & Scraper — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single Python script (`scripts/scrape_limitless.py`) that checks EN translation coverage for all JP sets, scrapes missing M* sets from Limitless TCG HTML, checks SV* set coverage via TCGdex API, and makes the minimal `app.js` changes needed to display Limitless CDN images and the new ME2a sideload.

**Architecture:** The script has three modes: (1) check existing `data/ME*.json` quality for M* sets, (2) scrape Limitless TCG HTML pages for sets with missing/incomplete EN translations and write `data/ME*.json` files, (3) verify SV* set coverage via TCGdex API. A hardcoded `SET_CONFIG` dict maps JP set IDs to EN sideload metadata. The `app.js` changes are two small edits: a one-line fix in `renderCard()` for full-URL images, and config additions for the new ME2a sideload.

**Tech Stack:** Python 3, requests, BeautifulSoup4 (html.parser), TCGdex REST API, JavaScript (app.js edits)

---

### Task 1: Bootstrap the script with config and coverage checker for M* sets

**Files:**
- Create: `scripts/scrape_limitless.py`

- [ ] **Step 1.1: Create the script file with imports, constants, and SET_CONFIG**

```python
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
```

- [ ] **Step 1.2: Implement `check_m_coverage()` and `check_all_m_sets()`**

Append to the script:

```python
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
        print(f"  {jp_set_id:4s} \u2192 {en_set_id:4s}: {status_icon} {result['reason']}")
        results[jp_set_id] = result
    print()
    return results
```

- [ ] **Step 1.3: Add a temporary `__main__` block to test the coverage checker**

Append to the script:

```python
if __name__ == "__main__":
    check_all_m_sets()
```

- [ ] **Step 1.4: Verify the coverage checker runs**

```bash
cd /home/ec2-user/pokemon-tcg-jp-en-matcher && python3 scripts/scrape_limitless.py
```

Expected output: a table showing each M* set's coverage status. ME1/ME2/ME3/ME4 should show existing status; ME2a should show "missing" since no `data/ME2a.json` exists yet.

---

### Task 2: Implement the Limitless HTML parser

**Files:**
- Modify: `scripts/scrape_limitless.py`

- [ ] **Step 2.1: Implement `fetch_card_page()` to download a single card page**

Insert before the `check_m_coverage` function:

```python
def fetch_card_page(jp_set_id: str, card_num: int) -> str | None:
    """Fetch a single card page from Limitless TCG with English translation."""
    url = f"{LIMITLESS_BASE}/{jp_set_id}/{card_num}?translate=en"
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        print(f"    ERROR fetching {url}: {e}")
        return None
```

- [ ] **Step 2.2: Implement `parse_energy_cost()` helper**

Insert after `fetch_card_page`:

```python
def parse_energy_cost(cost_el) -> list[str]:
    """
    Parse energy cost from a Limitless card page element.
    Limitless renders energy as <span> or <abbr> elements with single-letter text
    (G, R, W, L, P, F, D, M, C, N, Y) or as img alt text.
    """
    costs = []
    if cost_el is None:
        return costs

    # Try finding energy icon elements (spans/abbrs with single-letter content)
    for el in cost_el.find_all(["span", "abbr", "img"]):
        text = el.get_text(strip=True) if el.name != "img" else el.get("alt", "")
        if len(text) == 1 and text.upper() in ENERGY_MAP:
            costs.append(ENERGY_MAP[text.upper()])
        elif text.upper() in ENERGY_MAP:
            costs.append(ENERGY_MAP[text.upper()])

    # Fallback: scan raw text for single energy letters if no structured elements found
    if not costs:
        raw = cost_el.get_text(strip=True)
        for ch in raw:
            if ch.upper() in ENERGY_MAP:
                costs.append(ENERGY_MAP[ch.upper()])

    return costs
```

- [ ] **Step 2.3: Implement `parse_card_page()` to extract card data from HTML**

Insert after `parse_energy_cost`:

```python
def parse_card_page(html: str, jp_set_id: str, card_num: int, cfg: dict) -> dict | None:
    """
    Parse a Limitless TCG card page HTML into our card schema dict.

    Returns the card dict or None if parsing fails.
    """
    soup = BeautifulSoup(html, "html.parser")
    en_set_id = cfg["en_set_id"]
    en_set_name = cfg["en_set_name"]
    num_str = f"{card_num:03d}"

    # --- Card name ---
    # Limitless shows the translated name in the card detail header
    name_el = soup.select_one("h1, .card-name, .card-text-name")
    if not name_el:
        # Try the page title
        title_el = soup.find("title")
        if title_el:
            name = title_el.get_text(strip=True).split("|")[0].split("-")[0].strip()
        else:
            print(f"    WARNING: Could not find card name for {jp_set_id}/{card_num}")
            return None
    else:
        name = name_el.get_text(strip=True)

    # Clean up name: remove set number suffix if present (e.g., "Weedle 001/083")
    import re
    name = re.sub(r'\s*\d{1,3}\s*/\s*\d{1,3}\s*$', '', name).strip()
    # Remove "- Pokemon - Basic" suffixes sometimes included
    name = re.sub(r'\s*[-\u2013]\s*(Pokemon|Trainer|Energy)\b.*$', '', name, flags=re.IGNORECASE).strip()

    # --- Image URL ---
    # Look for the Limitless CDN image
    image_url = None
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if "limitlesstcg.nyc3.cdn.digitaloceanspaces.com" in src:
            image_url = src
            break
    # Also check data-src for lazy-loaded images
    if not image_url:
        for img in soup.find_all("img"):
            src = img.get("data-src", "")
            if "limitlesstcg.nyc3.cdn.digitaloceanspaces.com" in src:
                image_url = src
                break

    # --- Determine card category ---
    page_text = soup.get_text()

    # Look for category indicators in the card info section
    card_info = soup.select_one(".card-text, .card-info, .card-text-section")
    info_text = card_info.get_text() if card_info else page_text

    category = "Pokemon"
    subcategory = None
    stage = None

    # Check for Trainer subtypes
    trainer_keywords = {
        "Supporter": "Supporter",
        "Item": "Item",
        "Pokemon Tool": "Pokemon Tool",
        "Pokémon Tool": "Pokemon Tool",
        "Stadium": "Stadium",
    }
    for keyword, subcat in trainer_keywords.items():
        if f"Trainer - {keyword}" in info_text or f"Trainer\n{keyword}" in info_text:
            category = "Trainer"
            subcategory = subcat
            break

    # Check for Energy
    if "Energy - Special" in info_text or "Special Energy" in info_text:
        category = "Energy"
        subcategory = "Special Energy"
    elif "Energy - Basic" in info_text or "Basic Energy" in info_text:
        category = "Energy"
        subcategory = "Basic Energy"

    # If still Pokemon, check for "Trainer" without subtype match
    if category == "Pokemon" and re.search(r'\bTrainer\b', info_text):
        # Only reclassify if there's no HP (trainers don't have HP)
        hp_match = re.search(r'\b(\d{2,3})\s*HP\b', info_text)
        if not hp_match:
            category = "Trainer"

    # --- Build base card dict ---
    card = {
        "name": name,
        "id": f"{en_set_id}-{num_str}",
        "set": {"id": en_set_id, "name": en_set_name},
        "image": image_url,
        "category": category,
    }

    # --- Illustrator ---
    # Look for illustrator info
    illust_el = soup.find(string=re.compile(r'Illus\.?'))
    if illust_el:
        parent = illust_el.parent if illust_el.parent else None
        if parent:
            # The illustrator name is usually the next sibling or a link
            link = parent.find("a") if parent.name != "a" else parent
            if link:
                card["illustrator"] = link.get_text(strip=True)
            else:
                text = parent.get_text(strip=True)
                text = re.sub(r'^Illus\.?\s*', '', text).strip()
                if text:
                    card["illustrator"] = text

    # --- Rarity ---
    rarity = None
    rarity_el = soup.find(string=re.compile(r'(Common|Uncommon|Rare|Double Rare|Illustration Rare|Special Illustration Rare|Hyper Rare|Ultra Rare)', re.IGNORECASE))
    if rarity_el:
        match = re.search(r'(Common|Uncommon|(?:Special Illustration|Illustration|Double|Hyper|Ultra|Mega Hyper|Mega Art|Black White)?\s*Rare)', rarity_el.strip(), re.IGNORECASE)
        if match:
            rarity = match.group(1).strip().title()
    if rarity:
        card["rarity"] = rarity

    # --- Pokemon-specific fields ---
    if category == "Pokemon":
        # HP
        hp_match = re.search(r'\b(\d{2,3})\s*HP\b', info_text)
        if hp_match:
            card["hp"] = int(hp_match.group(1))

        # Types
        # Limitless shows the Pokemon type near HP
        types = []
        type_names = ["Grass", "Fire", "Water", "Lightning", "Psychic", "Fighting",
                       "Darkness", "Metal", "Dragon", "Fairy", "Colorless"]
        # Look for type indicators before/after HP
        for tn in type_names:
            if re.search(rf'\b{tn}\b.*\bHP\b|\bHP\b.*\b{tn}\b', info_text):
                types.append(tn)
                break
        # Also check for type icons
        if not types:
            for el in soup.select(".pokemon-type, .card-type, .type-icon"):
                text = el.get_text(strip=True)
                for tn in type_names:
                    if tn.lower() in text.lower():
                        types.append(tn)
        if types:
            card["types"] = types

        # Stage
        stage_patterns = {
            "Basic": r'\bBasic\b',
            "Stage1": r'\bStage\s*1\b',
            "Stage2": r'\bStage\s*2\b',
            "Mega": r'\bMega\b',
            "VSTAR": r'\bVSTAR\b',
            "VMAX": r'\bVMAX\b',
            "V": r'\b(?<!Mega )V\b',
        }
        for stage_name, pattern in stage_patterns.items():
            if re.search(pattern, info_text):
                stage = stage_name
                break
        if stage:
            card["stage"] = stage

        card["retreat"] = 0
        card["dexId"] = []

        # --- Attacks ---
        attacks = parse_attacks(soup)
        if attacks:
            card["attacks"] = attacks

        # --- Abilities ---
        abilities = parse_abilities(soup)
        if abilities:
            card["abilities"] = abilities

        # --- Weakness ---
        weakness = parse_weakness(soup, info_text)
        if weakness:
            card["weakness"] = weakness

        # --- Resistance ---
        resistance = parse_resistance(soup, info_text)
        if resistance:
            card["resistance"] = resistance

        # --- Retreat cost ---
        retreat = parse_retreat(soup, info_text)
        if retreat is not None:
            card["retreat"] = retreat

    else:
        # Trainer / Energy
        if subcategory:
            card["subcategory"] = subcategory

        # Extract effect text
        effect = parse_effect_text(soup)
        if effect:
            card["effect"] = effect

    return card


def parse_attacks(soup: BeautifulSoup) -> list[dict]:
    """Parse attack blocks from the card page."""
    import re
    attacks = []

    # Limitless renders attacks in structured blocks
    # Look for attack sections: elements with attack name, cost, damage, effect
    attack_sections = soup.select(".card-text-attack, .attack-info, [class*='attack']")

    if attack_sections:
        for section in attack_sections:
            attack = _parse_attack_section(section)
            if attack:
                attacks.append(attack)
    else:
        # Fallback: parse from the card text content block
        # Attacks typically appear after abilities and before weakness/resistance
        text_block = soup.select_one(".card-text, .card-text-section")
        if text_block:
            attacks = _parse_attacks_from_text_block(text_block)

    return attacks


def _parse_attack_section(section) -> dict | None:
    """Parse a single structured attack section element."""
    import re

    text = section.get_text(separator=" ", strip=True)
    if not text or len(text) < 2:
        return None

    attack = {}

    # Energy cost: look for cost sub-elements
    cost_el = section.select_one(".attack-cost, .energy-cost, [class*='cost']")
    if cost_el:
        attack["cost"] = parse_energy_cost(cost_el)
    else:
        # Try parsing cost letters from the beginning of text
        cost = []
        remaining = text
        for ch in text:
            if ch.upper() in ENERGY_MAP:
                cost.append(ENERGY_MAP[ch.upper()])
            else:
                break
        if cost:
            attack["cost"] = cost
            remaining = text[len(cost):]

    # Name: look for name sub-element
    name_el = section.select_one(".attack-name, [class*='name']")
    if name_el:
        attack["name"] = name_el.get_text(strip=True)
    else:
        # Name is the first non-cost, non-damage text
        parts = text.split()
        name_parts = []
        for p in parts:
            if p.upper() in ENERGY_MAP and not name_parts:
                continue
            if re.match(r'^\d+[+x\u00d7\u2212-]?$', p) and name_parts:
                break
            name_parts.append(p)
        if name_parts:
            attack["name"] = " ".join(name_parts)

    # Damage
    damage_el = section.select_one(".attack-damage, .damage, [class*='damage']")
    damage_text = damage_el.get_text(strip=True) if damage_el else None
    if not damage_text:
        damage_match = re.search(r'\b(\d{1,3})([+x\u00d7\u2212-])?\s*$', text)
        if damage_match:
            damage_text = damage_match.group(0).strip()

    if damage_text:
        num_match = re.match(r'^(\d+)', damage_text)
        if num_match:
            attack["damage"] = int(num_match.group(1))

    # Effect text
    effect_el = section.select_one(".attack-effect, .effect, [class*='effect']")
    if effect_el:
        effect = effect_el.get_text(strip=True)
        if effect:
            attack["effect"] = effect

    if not attack.get("name"):
        return None

    return attack


def _parse_attacks_from_text_block(text_block) -> list[dict]:
    """Fallback: parse attacks from a generic text block."""
    import re
    attacks = []

    # Get all text content and try to identify attack patterns
    # Pattern: [cost letters] AttackName [damage] \n [effect text]
    lines = text_block.get_text(separator="\n").split("\n")
    lines = [l.strip() for l in lines if l.strip()]

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check if this line looks like an attack header: starts with energy letters
        # followed by a name and optionally damage
        match = re.match(
            r'^([GRWLPFDMCNY]+)\s+(.+?)(?:\s+(\d{1,3}[+x\u00d7\u2212-]?))?$',
            line
        )
        if match:
            cost_str, name, damage_str = match.groups()
            attack = {
                "name": name.strip(),
                "cost": [ENERGY_MAP.get(c, c) for c in cost_str],
            }
            if damage_str:
                num_m = re.match(r'^(\d+)', damage_str)
                if num_m:
                    attack["damage"] = int(num_m.group(1))

            # Check next line for effect text (not an attack header or keyword)
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                if not re.match(r'^[GRWLPFDMCNY]+\s+', next_line) and \
                   not re.match(r'^(Weakness|Resistance|Retreat|Ability)', next_line, re.IGNORECASE):
                    attack["effect"] = next_line
                    i += 1

            attacks.append(attack)
        i += 1

    return attacks


def parse_abilities(soup: BeautifulSoup) -> list[dict]:
    """Parse ability blocks from the card page."""
    abilities = []

    # Look for ability sections
    ability_sections = soup.select(".card-text-ability, .ability-info, [class*='ability']")

    if ability_sections:
        for section in ability_sections:
            name_el = section.select_one(".ability-name, [class*='name']")
            effect_el = section.select_one(".ability-effect, .effect, [class*='effect']")

            name = name_el.get_text(strip=True) if name_el else None
            effect = effect_el.get_text(strip=True) if effect_el else None

            if not name:
                text = section.get_text(strip=True)
                # Try to split "Ability: Name\nEffect text"
                import re
                m = re.match(r'(?:Ability:?\s*)?(.+?)(?:\n|$)(.*)', text, re.DOTALL)
                if m:
                    name = m.group(1).strip()
                    if not effect:
                        effect = m.group(2).strip()

            if name:
                ability = {"name": name}
                if effect:
                    ability["effect"] = effect
                abilities.append(ability)
    else:
        # Fallback: look for "Ability" keyword in text
        import re
        text_block = soup.select_one(".card-text, .card-text-section")
        if text_block:
            text = text_block.get_text(separator="\n")
            for m in re.finditer(r'Ability:?\s*(.+?)\n(.+?)(?=\n[GRWLPFDMCNY]+\s|\nAbility|\nWeakness|\Z)', text, re.DOTALL):
                abilities.append({
                    "name": m.group(1).strip(),
                    "effect": " ".join(m.group(2).split()),
                })

    return abilities


def parse_weakness(soup: BeautifulSoup, info_text: str) -> dict | None:
    """Parse weakness from the card page."""
    import re

    # Look for weakness section
    weakness_el = soup.find(string=re.compile(r'Weakness', re.IGNORECASE))
    if weakness_el:
        parent = weakness_el.parent
        if parent:
            text = parent.get_text(strip=True)
            # Pattern: "Weakness: Fire x2" or "Weakness Fire ×2"
            for type_name in ["Grass", "Fire", "Water", "Lightning", "Psychic",
                              "Fighting", "Darkness", "Metal", "Dragon", "Fairy"]:
                if type_name in text:
                    return {"type": type_name, "value": "x2"}

            # Check sibling elements for type icon
            siblings = parent.find_next_siblings()
            for sib in siblings[:3]:
                sib_text = sib.get_text(strip=True)
                for type_name in ["Grass", "Fire", "Water", "Lightning", "Psychic",
                                  "Fighting", "Darkness", "Metal", "Dragon", "Fairy"]:
                    if type_name.lower() in sib_text.lower():
                        return {"type": type_name, "value": "x2"}

    # Fallback regex on full info text
    m = re.search(r'Weakness:?\s*(Grass|Fire|Water|Lightning|Psychic|Fighting|Darkness|Metal|Dragon|Fairy)', info_text, re.IGNORECASE)
    if m:
        return {"type": m.group(1).title(), "value": "x2"}

    return None


def parse_resistance(soup: BeautifulSoup, info_text: str) -> dict | None:
    """Parse resistance from the card page."""
    import re

    resistance_el = soup.find(string=re.compile(r'Resistance', re.IGNORECASE))
    if resistance_el:
        parent = resistance_el.parent
        if parent:
            text = parent.get_text(strip=True)
            for type_name in ["Grass", "Fire", "Water", "Lightning", "Psychic",
                              "Fighting", "Darkness", "Metal", "Dragon", "Fairy"]:
                if type_name in text:
                    # Extract value (usually -30)
                    val_m = re.search(r'[-\u2212](\d+)', text)
                    value = f"-{val_m.group(1)}" if val_m else "-30"
                    return {"type": type_name, "value": value}

    m = re.search(r'Resistance:?\s*(Grass|Fire|Water|Lightning|Psychic|Fighting|Darkness|Metal|Dragon|Fairy)\s*[-\u2212](\d+)', info_text, re.IGNORECASE)
    if m:
        return {"type": m.group(1).title(), "value": f"-{m.group(2)}"}

    return None


def parse_retreat(soup: BeautifulSoup, info_text: str) -> int | None:
    """Parse retreat cost from the card page."""
    import re

    retreat_el = soup.find(string=re.compile(r'Retreat', re.IGNORECASE))
    if retreat_el:
        parent = retreat_el.parent
        if parent:
            text = parent.get_text(strip=True)
            # Count Colorless energy symbols or look for a number
            c_count = text.count("C") + text.count("Colorless")
            if c_count > 0:
                return c_count
            num_m = re.search(r'Retreat:?\s*(\d+)', text, re.IGNORECASE)
            if num_m:
                return int(num_m.group(1))

            # Check next sibling for cost icons
            nxt = parent.find_next_sibling()
            if nxt:
                cost = parse_energy_cost(nxt)
                if cost:
                    return len(cost)

    m = re.search(r'Retreat\s*(?:Cost)?:?\s*(\d+)', info_text, re.IGNORECASE)
    if m:
        return int(m.group(1))

    return 0


def parse_effect_text(soup: BeautifulSoup) -> str | None:
    """Parse effect text for Trainer/Energy cards."""
    # Look for effect section
    effect_el = soup.select_one(".card-text-effect, .card-effect, [class*='effect']")
    if effect_el:
        text = effect_el.get_text(strip=True)
        if text:
            return text

    # Fallback: look for the main text block content (skip name/category lines)
    text_block = soup.select_one(".card-text, .card-text-section")
    if text_block:
        paragraphs = text_block.find_all("p")
        effects = [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]
        if effects:
            return " ".join(effects)

    return None
```

- [ ] **Step 2.4: Add a test function to parse a single card**

Append before the `if __name__` block:

```python
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
```

- [ ] **Step 2.5: Update `__main__` to accept a `--test-card` flag**

Replace the `if __name__` block:

```python
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Limitless TCG Coverage Checker & Scraper")
    parser.add_argument("--test-card", action="store_true", help="Test parsing a single card (M4/1)")
    parser.add_argument("--check-only", action="store_true", help="Only check coverage, don't scrape")
    parser.add_argument("--sets", type=str, help="Comma-separated JP set IDs to scrape (e.g. M4,M2a)")
    args = parser.parse_args()

    if args.test_card:
        test_single_card()
    else:
        check_all_m_sets()
```

- [ ] **Step 2.6: Verify the single-card test**

```bash
cd /home/ec2-user/pokemon-tcg-jp-en-matcher && python3 scripts/scrape_limitless.py --test-card
```

Inspect the JSON output. Verify the name is "Weedle", category is "Pokemon", HP is 50, type is Grass, has an attack with name "Surprise Attack". If fields are missing or wrong, adjust the parsing selectors based on the actual HTML structure.

- [ ] **Step 2.7: Refine parsing based on actual Limitless HTML**

After running `--test-card`, save the raw HTML for inspection and refine selectors as needed:

```bash
cd /home/ec2-user/pokemon-tcg-jp-en-matcher && python3 -c "
import requests
resp = requests.get('https://limitlesstcg.com/cards/jp/M4/1?translate=en', headers={'User-Agent': 'Mozilla/5.0'})
with open('/tmp/limitless_sample.html', 'w') as f:
    f.write(resp.text)
print(f'Saved {len(resp.text)} bytes to /tmp/limitless_sample.html')
"
```

Then examine the HTML structure and adjust the CSS selectors in `parse_card_page()`, `parse_attacks()`, `parse_abilities()`, etc. to match the actual DOM. The selectors in Step 2.3 are best-effort guesses based on the spec; Limitless may use different class names.

---

### Task 3: Implement the full set scraper

**Files:**
- Modify: `scripts/scrape_limitless.py`

- [ ] **Step 3.1: Implement `scrape_set()` — fetches all cards and builds the ME*.json structure**

Insert before `check_m_coverage`:

```python
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
                print(f"    [{num:3d}/{card_count}] {card['name']} ({card.get('category', '?')}) \u2713")
            else:
                failures.append(num)
                print(f"    [{num:3d}/{card_count}] Parse FAILED")
        else:
            failures.append(num)
            print(f"    [{num:3d}/{card_count}] Fetch FAILED")

        # Rate limit: 1 second between requests
        if num < card_count:
            time.sleep(1)

    if failures:
        print(f"  WARNING: {len(failures)} cards failed: {failures}")

    data = {
        "id": en_set_id,
        "name": en_set_name,
        "serie": cfg["serie"],
        "releaseDate": {"en": cfg["release_date"]},
        "jpSetId": jp_set_id,
        "cards": cards,
    }

    return data
```

- [ ] **Step 3.2: Implement `preserve_dex_ids()` — merges existing dexId values into scraped data**

Insert after `scrape_set`:

```python
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
            # Preserve dexId if the old card had one and the new one doesn't
            if old_card.get("dexId") and not card.get("dexId"):
                card["dexId"] = old_card["dexId"]
            elif old_card.get("dexId") and card.get("dexId") == []:
                card["dexId"] = old_card["dexId"]

    return new_data
```

- [ ] **Step 3.3: Implement `write_sideload()` — writes the ME*.json file**

Insert after `preserve_dex_ids`:

```python
def write_sideload(data: dict, cfg: dict):
    """Write the scraped data to data/ME*.json, preserving existing dexIds."""
    en_set_id = cfg["en_set_id"]
    file_path = DATA_DIR / f"{en_set_id}.json"

    data = preserve_dex_ids(data, file_path)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    card_count = len(data.get("cards", {}))
    print(f"  Done. Wrote {card_count} cards to {file_path}")
```

- [ ] **Step 3.4: Implement `scrape_missing_m_sets()` — orchestrates scraping for sets that need it**

Insert after `write_sideload`:

```python
def scrape_missing_m_sets(coverage: dict, only_sets: list[str] | None = None):
    """
    Scrape M* sets that have missing or incomplete EN coverage.

    Args:
        coverage: dict from check_all_m_sets()
        only_sets: if provided, only scrape these JP set IDs
    """
    # M1S and M1L both map to ME1 — only scrape once
    scraped_en_sets = set()

    for jp_set_id, result in coverage.items():
        cfg = SET_CONFIG[jp_set_id]
        en_set_id = cfg["en_set_id"]

        # Skip if user specified --sets and this isn't in the list
        if only_sets and jp_set_id not in only_sets:
            continue

        # Skip if already scraped this EN set (M1S/M1L both -> ME1)
        if en_set_id in scraped_en_sets:
            print(f"  {jp_set_id} -> {en_set_id}: Already scraped (from prior JP set)")
            continue

        if result["status"] in ("missing", "incomplete"):
            data = scrape_set(jp_set_id, cfg)
            write_sideload(data, cfg)
            scraped_en_sets.add(en_set_id)
        else:
            # Force scrape if user explicitly asked for this set
            if only_sets and jp_set_id in only_sets:
                print(f"  {jp_set_id} -> {en_set_id}: Coverage OK but --sets forces rescrape")
                data = scrape_set(jp_set_id, cfg)
                write_sideload(data, cfg)
                scraped_en_sets.add(en_set_id)
```

- [ ] **Step 3.5: Verify with a small scrape (first 3 cards of M4)**

```bash
cd /home/ec2-user/pokemon-tcg-jp-en-matcher && python3 -c "
import json, time
from scripts.scrape_limitless import fetch_card_page, parse_card_page, SET_CONFIG

cfg = SET_CONFIG['M4']
cards = {}
for num in range(1, 4):
    html = fetch_card_page('M4', num)
    if html:
        card = parse_card_page(html, 'M4', num, cfg)
        if card:
            cards[f'{num:03d}'] = card
            print(f'{num}: {card[\"name\"]} - {card.get(\"category\")} - attacks: {len(card.get(\"attacks\", []))}')
    time.sleep(1)
print(json.dumps(cards, indent=2, ensure_ascii=False))
"
```

---

### Task 4: Implement SV* coverage checker

**Files:**
- Modify: `scripts/scrape_limitless.py`

- [ ] **Step 4.1: Implement `check_sv_coverage()` — fetches SV sets from TCGdex and verifies EN matches**

Insert before `test_single_card`:

```python
def check_sv_coverage():
    """
    Check SV* set coverage via TCGdex API.
    For each SV set, pick a random card and check if an EN match exists.
    """
    print("=== SV* Coverage Check ===")

    # 1. Fetch all JP sets
    try:
        resp = requests.get(f"{TCGDEX_API}/ja/sets", timeout=15)
        resp.raise_for_status()
        all_sets = resp.json()
    except requests.RequestException as e:
        print(f"  ERROR fetching JP sets from TCGdex: {e}")
        return

    # 2. Filter SV* sets (skip deck/promo sets)
    sv_sets = []
    for s in all_sets:
        set_id = s.get("id", "")
        if set_id.upper().startswith("SV") and set_id.upper() not in SV_SKIP_IDS:
            sv_sets.append(s)

    if not sv_sets:
        print("  No SV* sets found in TCGdex.")
        return

    print(f"  Found {len(sv_sets)} SV* sets to check.\n")

    # 3. For each: pick a random card, check EN match
    for s in sorted(sv_sets, key=lambda x: x.get("id", "")):
        set_id = s.get("id", "")
        set_name = s.get("name", "?")

        try:
            # Fetch set details to get card list
            resp = requests.get(f"{TCGDEX_API}/ja/sets/{set_id}", timeout=15)
            resp.raise_for_status()
            set_data = resp.json()
            cards = set_data.get("cards", [])

            if not cards:
                print(f"  {set_id:8s} ({set_name:25s}): \u2753 No cards in set")
                time.sleep(0.5)
                continue

            # Pick a random Pokemon card (prefer cards with dexId)
            sample = random.choice(cards)
            card_id = sample.get("id", "")

            # Fetch full card details to get dexId
            resp = requests.get(f"{TCGDEX_API}/ja/cards/{card_id}", timeout=15)
            resp.raise_for_status()
            card_data = resp.json()
            dex_ids = card_data.get("dexId", [])
            card_name = card_data.get("name", "?")

            if not dex_ids:
                # Try to find EN card by name directly
                en_name = card_data.get("name", "")
                resp = requests.get(
                    f"{TCGDEX_API}/en/cards",
                    params={"name": en_name},
                    timeout=15,
                )
                resp.raise_for_status()
                en_cards = resp.json()
                if en_cards:
                    print(f"  {set_id:8s} ({set_name:25s}): \u2705 EN match found (name: {en_name})")
                else:
                    print(f"  {set_id:8s} ({set_name:25s}): \u2753 No dexId, name match inconclusive")
            else:
                # Look up EN name by dexId
                resp = requests.get(
                    f"{TCGDEX_API}/en/cards",
                    params={"dexId": dex_ids[0]},
                    timeout=15,
                )
                resp.raise_for_status()
                en_cards = resp.json()
                if en_cards:
                    en_name = en_cards[0].get("name", "?")
                    print(f"  {set_id:8s} ({set_name:25s}): \u2705 EN match found ({en_name})")
                else:
                    print(f"  {set_id:8s} ({set_name:25s}): \u274c No EN match (dexId={dex_ids[0]}, JP={card_name})")

        except requests.RequestException as e:
            print(f"  {set_id:8s} ({set_name:25s}): ERROR {e}")

        time.sleep(0.5)

    print()
```

- [ ] **Step 4.2: Verify the SV check runs**

```bash
cd /home/ec2-user/pokemon-tcg-jp-en-matcher && python3 -c "
from scripts.scrape_limitless import check_sv_coverage
check_sv_coverage()
" 2>&1 | head -20
```

---

### Task 5: Wire everything together + main() entry point

**Files:**
- Modify: `scripts/scrape_limitless.py`

- [ ] **Step 5.1: Replace the `if __name__` block with the full CLI**

Replace the entire `if __name__` block at the end of the file:

```python
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Limitless TCG Coverage Checker & Scraper",
        epilog="Examples:\n"
               "  python scrape_limitless.py                  # Check all + scrape missing M* + check SV*\n"
               "  python scrape_limitless.py --check-only     # Coverage report only\n"
               "  python scrape_limitless.py --sets M4,M2a    # Scrape specific sets\n"
               "  python scrape_limitless.py --test-card      # Test single card parse\n",
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
    args = parser.parse_args()

    if args.test_card:
        test_single_card()
        sys.exit(0)

    # 1. Check all M* sets
    coverage = check_all_m_sets()

    # 2. Scrape missing M* sets (unless --check-only)
    if not args.check_only:
        only_sets = [s.strip() for s in args.sets.split(",")] if args.sets else None
        scrape_missing_m_sets(coverage, only_sets)

    # 3. Check SV* coverage
    if not args.skip_sv:
        check_sv_coverage()

    print("Done.")
```

- [ ] **Step 5.2: Verify the full script runs in check-only mode**

```bash
cd /home/ec2-user/pokemon-tcg-jp-en-matcher && python3 scripts/scrape_limitless.py --check-only --skip-sv
```

- [ ] **Step 5.3: Verify the help text**

```bash
cd /home/ec2-user/pokemon-tcg-jp-en-matcher && python3 scripts/scrape_limitless.py --help
```

---

### Task 6: Fix `renderCard()` in app.js for full-URL images

**Files:**
- Modify: `app.js`

- [ ] **Step 6.1: Change the image URL construction in `renderCard()`**

In `app.js`, line 170, change:

```javascript
  const imgUrl = card.image ? card.image + '/high.webp' : sideloadImageUrl(card) || null;
```

to:

```javascript
  const imgUrl = card.image ? (card.image.startsWith('http') ? card.image : card.image + '/high.webp') : sideloadImageUrl(card) || null;
```

This handles both:
- **Limitless CDN URLs** (already full `.png` URLs starting with `https://`) — used as-is
- **TCGdex relative paths** (e.g., `https://assets.tcgdex.net/en/sv/sv1/5`) — still gets `/high.webp` appended

- [ ] **Step 6.2: Verify the change is syntactically correct**

```bash
cd /home/ec2-user/pokemon-tcg-jp-en-matcher && node -c app.js && echo "Syntax OK"
```

---

### Task 7: Update app.js config for ME2a

**Files:**
- Modify: `app.js`

- [ ] **Step 7.1: Add ME2a to `SIDELOAD_CONFIG.en`**

In `app.js`, inside the `SIDELOAD_CONFIG.en` array (around line 28-33), add the ME2a entry after ME4:

```javascript
    { id: "ME2a", name: "MEGA Dream ex",     file: "data/ME2a.json" },
```

The full `en` array becomes:

```javascript
  en: [
    { id: "ME1", name: "Mega Evolution",      file: "data/ME1.json" },
    { id: "ME2", name: "Phantasmal Flames",   file: "data/ME2.json" },
    { id: "ME3", name: "Perfect Order",       file: "data/ME3.json" },
    { id: "ME4", name: "Ninja Spinner",       file: "data/ME4.json" },
    { id: "ME2a", name: "MEGA Dream ex",     file: "data/ME2a.json" },
  ]
```

- [ ] **Step 7.2: Add M2A -> ME2a mapping to `JP_TO_EN_SIDELOAD`**

In `app.js`, line 41, change:

```javascript
const JP_TO_EN_SIDELOAD = { "M1S": "ME1", "M1L": "ME1", "M2": "ME2", "M3": "ME3", "M4": "ME4" };
```

to:

```javascript
const JP_TO_EN_SIDELOAD = { "M1S": "ME1", "M1L": "ME1", "M2": "ME2", "M2A": "ME2a", "M3": "ME3", "M4": "ME4" };
```

Note: The key is `"M2A"` (uppercase) because `JP_TO_EN_SIDELOAD` lookups use `jpSetId.toUpperCase()` — and `"M2a".toUpperCase()` is `"M2A"`.

- [ ] **Step 7.3: Verify syntax is still valid**

```bash
cd /home/ec2-user/pokemon-tcg-jp-en-matcher && node -c app.js && echo "Syntax OK"
```

- [ ] **Step 7.4: Verify the sideload config changes work at runtime**

Open `index.html` in a browser (or use a local server) and check:
1. The set dropdown includes ME2a
2. Searching for a M2a card shows the EN sideload result (once `data/ME2a.json` exists)
