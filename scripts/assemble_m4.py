#!/usr/bin/env python3
"""
Assemble final M4.json:
 - Cards 001-083: freshly scraped from pokemon-card.com (full JP data)
 - dexIds:        from ME4.json (already accurate)
 - Cards 084-120: alt-art variants rebuilt from base card game data
 - Alt-art metadata (name, rarity, dexId) sourced from git HEAD original
"""
import json
import subprocess
import sys

SET_ID   = "M4"
SET_NAME = "Ninja Spinner"

# ── Load scraped data (current data/M4.json has only 001-083) ───────────────
with open("data/M4.json", encoding="utf-8") as f:
    scraped = json.load(f)
# Only use cards 001-083 (base set) for game-data lookups; ignore any alt-art
# entries that may already be present if this script was run before.
base_cards = {k: v for k, v in scraped["cards"].items() if int(k) <= 83}

# ── Load ME4.json for dexIds ─────────────────────────────────────────────────
with open("data/ME4.json", encoding="utf-8") as f:
    me4 = json.load(f)
me4_cards = me4["cards"]        # dict: "001"→{name, dexId, …}

# Add dexIds to base cards (ME4 positions match M4 positions 1-83)
for num, card in base_cards.items():
    if num in me4_cards and "dexId" in me4_cards[num]:
        card["dexId"] = me4_cards[num]["dexId"]

# ── Load original M4.json from git (for alt-art card list 084-120) ──────────
git_out = subprocess.check_output(
    ["git", "show", "HEAD:data/M4.json"], stderr=subprocess.DEVNULL
)
orig = json.loads(git_out)
orig_cards = orig["cards"]

# ── Fix rarity labels the scraper couldn't resolve ───────────────────────────
RARITY_FIX = {
    "ic_rare_c_c": "Common",
    "ic_rare_u_c": "Uncommon",
    "ic_rare_r_c": "Rare",
}
for card in base_cards.values():
    if card["rarity"] in RARITY_FIX:
        card["rarity"] = RARITY_FIX[card["rarity"]]

# ── Build name→base_card index (JP name → scraped card dict) ────────────────
name_to_base: dict[str, dict] = {}
for card in base_cards.values():
    name_to_base[card["name"]] = card

# Also index by dexId for Pokémon cards (in case name spelling differs)
dex_to_base: dict[int, dict] = {}
for card in base_cards.values():
    for d in card.get("dexId", []):
        # Prefer the more-evolved version (higher card number) when multiple share dexId
        if d not in dex_to_base or card.get("stage","Basic") != "Basic":
            dex_to_base[d] = card

# Manual overrides: original alt-art name → scraped base card name
# (catches small differences like カエンジシex vs メガカエンジシex,
#  and English-localized names used in original data vs correct JP names in scrape)
NAME_OVERRIDE = {
    "カエンジシex":      "メガカエンジシex",
    "チラーミィex":      "チラチーノex",
    "AZのくつろぎ":      "AZの安らぎ",
    "フィリップ":        "ジプソ",
    "ホミカのパフォーマンス": "ホミカの演奏",
    "エマ":              "マチエール",
}

# ── Reconstruct alt-art cards ────────────────────────────────────────────────
GAME_FIELDS = ["hp", "types", "stage", "retreat", "attacks", "abilities",
               "weakness", "resistance", "subcategory", "effect"]

def find_base(orig_card: dict):
    name = orig_card["name"]
    # 1. direct name match
    if name in name_to_base:
        return name_to_base[name]
    # 2. manual override
    if name in NAME_OVERRIDE:
        mapped = NAME_OVERRIDE[name]
        if mapped in name_to_base:
            return name_to_base[mapped]
    # 3. dexId match (pick highest stage)
    for dex in orig_card.get("dexId") or []:
        if dex in dex_to_base:
            return dex_to_base[dex]
    return None


alt_cards: dict[str, dict] = {}
for num_str, orig_card in orig_cards.items():
    if int(num_str) <= 83:
        continue   # already in base_cards

    base = find_base(orig_card)
    new_card: dict = {
        "name":     orig_card["name"],
        "category": orig_card.get("category", "Pokemon"),
        "rarity":   orig_card["rarity"],
        "id":       f"{SET_ID}-{num_str}",
        "set":      {"id": SET_ID, "name": SET_NAME},
        "image":    None,
    }
    if orig_card.get("dexId"):
        new_card["dexId"] = orig_card["dexId"]

    if base:
        for field in GAME_FIELDS:
            if field in base:
                new_card[field] = base[field]
    else:
        # Fallback: copy game fields from original (may still be imperfect)
        print(f"  WARNING: no base found for {num_str} {orig_card['name']}")
        for field in GAME_FIELDS:
            if field in orig_card:
                new_card[field] = orig_card[field]

    alt_cards[num_str] = new_card

# ── Combine and sort ─────────────────────────────────────────────────────────
all_cards = {**base_cards, **alt_cards}
all_cards = dict(sorted(all_cards.items()))

# ── Write output ─────────────────────────────────────────────────────────────
output = {
    "id":          SET_ID,
    "name":        {"ja": SET_NAME},
    "serie":       "M",
    "releaseDate": {"ja": "2026-02-27"},
    "cards":       all_cards,
}

with open("data/M4.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"Wrote {len(all_cards)} cards to data/M4.json")

# ── Validation ───────────────────────────────────────────────────────────────
print("\n--- Validation ---")
missing_cost = []
for num, card in all_cards.items():
    for atk in card.get("attacks", []):
        if "cost" not in atk:
            missing_cost.append(f"{num} {card['name']}: {atk['name']}")

if missing_cost:
    print(f"FAIL: {len(missing_cost)} attacks still missing cost:")
    for m in missing_cost:
        print("  ", m)
else:
    print("OK: all attacks have cost arrays")

# Check rarity coverage
from collections import Counter
rarities = Counter(c["rarity"] for c in all_cards.values())
for r, cnt in sorted(rarities.items()):
    print(f"  {cnt:3d}  {r}")
