#!/usr/bin/env python3
"""Scrape all M5 Abyss Eye cards from pokemon-card.com and rebuild data/M5.json"""

import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

SET_ID = "M5"
SET_NAME = "Abyss Eye"
BASE_URL = "https://www.pokemon-card.com/card-search/details.php/card/{}/regu/XY"

# Fill these in on release day after running scripts/probe_m5_id_range.py
# (M4 was 50085–50204 for reference; M5 is expected to start at 50205 or later)
CARD_ID_START = None  # e.g. 50205
CARD_ID_END   = None  # e.g. 50285 for an 81-card main set; may be higher with secret rares

ICON_TO_TYPE = {
    "icon-grass":    "Grass",
    "icon-fire":     "Fire",
    "icon-water":    "Water",
    "icon-electric": "Lightning",
    "icon-psychic":  "Psychic",
    "icon-fighting": "Fighting",
    "icon-dark":     "Darkness",
    "icon-steel":    "Metal",
    "icon-dragon":   "Dragon",
    "icon-fairy":    "Fairy",
    "icon-none":     "Colorless",
}

RARITY_MAP = {
    "ic_rare_r_c":  "Rare",
    "ic_rare_c":    "Common",
    "ic_rare_u_c":  "Uncommon",
    "ic_rare_u":    "Uncommon",
    "ic_rare_r":    "Rare",
    "ic_rare_rr":   "Double Rare",
    "ic_rare_ar":   "Illustration Rare",
    "ic_rare_sr":   "Special Illustration Rare",
    "ic_rare_sar":  "Special Illustration Rare",
    "ic_rare_ur":   "Hyper Rare",
    "ic_rare_mur":  "Mega Hyper Rare",
    "ic_rare_ma":   "Mega Art Rare",
    "ic_rare_bwr":  "Black White Rare",
}

STAGE_MAP = {
    "たね":     "Basic",
    "1 進化":   "Stage1",
    "2 進化":   "Stage2",
    "メガシンカ": "Mega",
    "LEGEND":   "Legend",
    "VSTAR":    "VSTAR",
    "VMAX":     "VMAX",
    "V":        "V",
}

TRAINER_SUBTYPES = {
    "グッズ":           "Item",
    "ポケモンのどうぐ":  "Pokemon Tool",
    "サポート":         "Supporter",
    "スタジアム":       "Stadium",
}


def get_icons(html_fragment):
    icons = re.findall(r'class="(icon-[a-z]+) icon"', html_fragment)
    return [ICON_TO_TYPE.get(i, i) for i in icons]


def strip_tags(html):
    text = re.sub(r'<[^>]+>', '', html)
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').strip()
    return re.sub(r'\s+', ' ', text)


def parse_card(card_id):
    url = BASE_URL.format(card_id)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8')
    except Exception as e:
        print(f"  ERROR fetching {card_id}: {e}")
        return None

    m = re.search(r'<section class="Section">(.*?)</section>', html, re.DOTALL)
    if not m:
        print(f"  ERROR: no Section found for {card_id}")
        return None
    section = m.group(1)

    name_m = re.search(r'<h1 class="Heading1 mt20">([^<]+)</h1>', html)
    if not name_m:
        return None
    name = name_m.group(1).strip()

    num_m = re.search(r'&nbsp;(\d+)&nbsp;/&nbsp;(\d+)&nbsp;', section)
    if not num_m:
        return None
    card_num = int(num_m.group(1))

    illust_m = re.search(r'<a[^>]+illust=([^&"]+)[^>]*>([^<]+)</a>', html)
    illustrator = illust_m.group(2).strip() if illust_m else None

    rarity_m = re.search(r'src="/assets/images/card/rarity/(ic_rare_[^.]+)\.gif"', section)
    rarity = "Unknown"
    if rarity_m:
        rarity_key = rarity_m.group(1)
        rarity = RARITY_MAP.get(rarity_key, rarity_key)

    right_m = re.search(r'<div class="RightBox">(.*?)<div class="clear">', section, re.DOTALL)
    if not right_m:
        return None
    right = right_m.group(1)

    stage = None
    stage_m = re.search(r'<span class="type">([^<]+)</span>', right)
    if stage_m:
        raw_stage = stage_m.group(1).replace('&nbsp;', ' ').strip()
        stage = STAGE_MAP.get(raw_stage, raw_stage)

    hp = None
    hp_m = re.search(r'<span class="hp-num">(\d+)</span>', right)
    if hp_m:
        hp = int(hp_m.group(1))

    types = []
    type_m = re.search(r'<span class="hp-type">タイプ</span>(.*?)</div>', right, re.DOTALL)
    if type_m:
        types = get_icons(type_m.group(1))

    category = "Pokemon"
    trainer_subtype = None
    subcategory_m = re.search(r'<h2 class="mt20">(グッズ|ポケモンのどうぐ|サポート|スタジアム|特殊エネルギー|基本エネルギー)</h2>', right)
    if subcategory_m:
        sub = subcategory_m.group(1)
        if sub == "特殊エネルギー" or sub == "基本エネルギー":
            category = "Energy"
            trainer_subtype = "Special Energy" if sub == "特殊エネルギー" else "Basic Energy"
        else:
            category = "Trainer"
            trainer_subtype = TRAINER_SUBTYPES.get(sub, sub)

    abilities = []
    ability_blocks = re.findall(r'<h2 class="mt20">特性</h2>\s*<h4>([^<]+)</h4>\s*<p>(.*?)</p>', right, re.DOTALL)
    for ab_name, ab_effect in ability_blocks:
        abilities.append({
            "name": ab_name.strip(),
            "effect": strip_tags(ab_effect),
        })

    attacks = []
    waza_sections = re.findall(r'<h2 class="mt20">ワザ</h2>(.*?)(?=<h2 |$)', right, re.DOTALL)
    for waza_block in waza_sections:
        attack_pattern = re.finditer(
            r'<h4>(.*?)</h4>\s*(?:<p>(.*?)</p>)?',
            waza_block, re.DOTALL
        )
        for am in attack_pattern:
            h4 = am.group(1)
            effect_html = am.group(2) or ""

            cost = get_icons(h4)

            dmg_m = re.search(r'<span class="f_right[^"]*">([^<]+)</span>', h4)
            damage_str = dmg_m.group(1).strip() if dmg_m else ""

            h4_no_icons = re.sub(r'<span class="(?:icon-[a-z]+ icon|f_right[^"]*)">[^<]*</span>', '', h4)
            attack_name = strip_tags(h4_no_icons).strip()

            if not attack_name:
                continue

            attack = {"name": attack_name, "cost": cost}

            if damage_str:
                num_m = re.match(r'^(\d+)', damage_str)
                if num_m:
                    attack["damage"] = int(num_m.group(1))
                    suffix = damage_str[num_m.end():]
                    if suffix:
                        attack["damageModifier"] = suffix
                else:
                    attack["damageText"] = damage_str

            effect = strip_tags(effect_html).strip()
            if effect:
                attack["effect"] = effect

            attacks.append(attack)

    weakness = None
    resistance = None
    retreat = 0

    table_m = re.search(r'<table[^>]*>(.*?)</table>', right, re.DOTALL)
    if table_m:
        table = table_m.group(1)
        tds = re.findall(r'<td[^>]*>(.*?)</td>', table, re.DOTALL)
        if len(tds) >= 3:
            wk = tds[0]
            wk_icons = get_icons(wk)
            wk_val_m = re.search(r'[×x](\d+)', wk)
            if wk_icons and wk_val_m:
                weakness = {"type": wk_icons[0], "value": f"x{wk_val_m.group(1)}"}
            rs = tds[1]
            rs_icons = get_icons(rs)
            rs_val_m = re.search(r'[－-](\d+)', rs)
            if rs_icons and rs_val_m:
                resistance = {"type": rs_icons[0], "value": f"-{rs_val_m.group(1)}"}
            rt = tds[2]
            rt_icons = get_icons(rt)
            retreat = len(rt_icons)

    card_num_str = f"{card_num:03d}"
    card = {
        "name": name,
        "category": category,
        "rarity": rarity,
        "id": f"{SET_ID}-{card_num_str}",
        "set": {"id": SET_ID, "name": SET_NAME},
        "image": None,
    }
    if illustrator:
        card["illustrator"] = illustrator

    if category == "Pokemon":
        if hp is not None:
            card["hp"] = hp
        if types:
            card["types"] = types
        if stage:
            card["stage"] = stage
        card["retreat"] = retreat
        if abilities:
            card["abilities"] = abilities
        if attacks:
            card["attacks"] = attacks
        if weakness:
            card["weakness"] = weakness
        if resistance:
            card["resistance"] = resistance
    else:
        if trainer_subtype:
            card["subcategory"] = trainer_subtype
        all_p = re.findall(r'<p>(.*?)</p>', right, re.DOTALL)
        effects = [strip_tags(p) for p in all_p if strip_tags(p)]
        if effects:
            card["effect"] = " ".join(effects)

    return card_num_str, card


def main():
    if CARD_ID_START is None or CARD_ID_END is None:
        print("ERROR: CARD_ID_START / CARD_ID_END are not set.")
        print("Run scripts/probe_m5_id_range.py first, then edit this file's constants.")
        sys.exit(2)

    total = CARD_ID_END - CARD_ID_START + 1
    print(f"Fetching {total} M5 cards from pokemon-card.com...")
    results = {}

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(parse_card, cid): cid
            for cid in range(CARD_ID_START, CARD_ID_END + 1)
        }
        for i, future in enumerate(as_completed(futures), 1):
            card_id = futures[future]
            result = future.result()
            if result:
                num, card = result
                results[num] = card
                print(f"  [{i:3d}/{total}] {card_id} → {num}: {card['name']} ({card['rarity']})")
            else:
                print(f"  [{i:3d}/{total}] {card_id} → FAILED")

    sorted_cards = dict(sorted(results.items()))

    data = {
        "id": SET_ID,
        "name": {"ja": SET_NAME},
        "serie": "M",
        "releaseDate": {"ja": "2026-05-22"},
        "cards": sorted_cards,
    }

    out_path = "data/M5.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nDone! Wrote {len(sorted_cards)} cards to {out_path}")

    missing = []
    for num, card in sorted_cards.items():
        if card["category"] == "Pokemon":
            for atk in card.get("attacks", []):
                if not atk.get("cost") and atk.get("cost") != []:
                    missing.append(f"{num} {card['name']}: {atk['name']}")
    if missing:
        print("WARNING - attacks still missing cost:")
        for m in missing:
            print(" ", m)
    else:
        print("All Pokemon attacks have cost arrays.")


if __name__ == "__main__":
    main()
