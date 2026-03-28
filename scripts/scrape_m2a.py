#!/usr/bin/env python3
"""Scrape all 193 MEGAドリームex (M2a) cards from pokemon-card.com and build data/M2a.json"""

import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

SET_ID = "M2a"
SET_NAME = "MEGAドリームex"
BASE_URL = "https://www.pokemon-card.com/card-search/details.php/card/{}/regu/XY"
CARD_ID_START = 48523   # card 001/193
CARD_ID_END   = 48715   # card 193/193

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

STAGE_MAP = {
    "たね":       "Basic",
    "1 進化":     "Stage1",
    "2 進化":     "Stage2",
    "メガシンカ": "Mega",
    "BREAK":      "BREAK",
    "LEGEND":     "Legend",
    "VSTAR":      "VSTAR",
    "VMAX":       "VMAX",
    "V":          "V",
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
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    return re.sub(r'\s+', ' ', text).strip()


def parse_card(card_id):
    url = BASE_URL.format(card_id)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8')
    except Exception as e:
        print(f"  ERROR fetching {card_id}: {e}")
        return None

    # Extract the main section
    section_m = re.search(r'<section class="Section">(.*?)</section>', html, re.DOTALL)
    if not section_m:
        return None
    section = section_m.group(1)

    # --- Card name ---
    name_m = re.search(r'<h1 class="Heading1 mt20">([^<]+)</h1>', html)
    if not name_m:
        return None
    name = name_m.group(1).strip()

    # --- Card number ---
    num_m = re.search(r'&nbsp;(\d+)&nbsp;/&nbsp;(\d+)&nbsp;', section)
    if not num_m:
        return None
    card_num = int(num_m.group(1))

    # --- LeftBox: description, dexId, illustrator ---
    left_m = re.search(r'<div class="LeftBox">(.*?)</div>\s*<div class="RightBox">', section, re.DOTALL)
    description = None
    dex_id = None
    illustrator = None

    if left_m:
        left = left_m.group(1)
        # Illustrator
        illust_m = re.search(r'<a[^>]+illust=([^&"]+)[^>]*>([^<]+)</a>', left)
        if illust_m:
            illustrator = illust_m.group(2).strip()
        # Dex number
        dex_m = re.search(r'No\.(\d+)', left)
        if dex_m:
            dex_id = int(dex_m.group(1))
        # Description: <p> after <hr />
        desc_m = re.search(r'<hr\s*/>\s*<p>(.*?)</p>', left, re.DOTALL)
        if desc_m:
            description = strip_tags(desc_m.group(1))

    # --- evolveFrom: parse evolution chain block ---
    # Chain order (top-down): highest stage → current (ev_on) → basic.
    # Parallel forms share an "evbox" container with in-box divs (skip those for pre-evo lookup).
    # We look for "evolution ev_off" entries only (not in-box) after ev_on to get the pre-evolution.
    evolve_from = None
    chain_entries = []  # (is_parallel, cls, name)
    for m in re.finditer(
        r'<div class="([^"]*\bev_o(?:n|ff)\b[^"]*)">\s*<a[^>]*>([^<]+)</a>',
        section
    ):
        full_class = m.group(1)
        cls = "ev_on" if "ev_on" in full_class else "ev_off"
        is_parallel = "in-box" in full_class  # in-box = parallel form, not chain step
        evo_name = m.group(2).strip()
        chain_entries.append((is_parallel, cls, evo_name))

    if chain_entries:
        found_current = False
        for is_parallel, cls, evo_name in chain_entries:
            if cls == "ev_on":
                found_current = True
            elif cls == "ev_off" and found_current and not is_parallel:
                # First non-parallel ev_off after ev_on = pre-evolution
                evolve_from = evo_name
                break

    # --- RightBox ---
    right_m = re.search(r'<div class="RightBox">(.*?)<div class="clear">', section, re.DOTALL)
    if not right_m:
        return None
    right = right_m.group(1)

    # --- Stage ---
    stage = None
    stage_m = re.search(r'<span class="type">([^<]+)</span>', right)
    if stage_m:
        raw_stage = stage_m.group(1).replace('&nbsp;', ' ').strip()
        stage = STAGE_MAP.get(raw_stage, raw_stage)

    # --- HP ---
    hp = None
    hp_m = re.search(r'<span class="hp-num">(\d+)</span>', right)
    if hp_m:
        hp = int(hp_m.group(1))

    # --- Types ---
    types = []
    type_m = re.search(r'<span class="hp-type">タイプ</span>(.*?)</div>', right, re.DOTALL)
    if type_m:
        types = get_icons(type_m.group(1))

    # --- Category and trainer subtype ---
    category = "Pokemon"
    trainer_subtype = None
    subcategory_m = re.search(
        r'<h2 class="mt20">(グッズ|ポケモンのどうぐ|サポート|スタジアム|特殊エネルギー|基本エネルギー)</h2>', right
    )
    if subcategory_m:
        sub = subcategory_m.group(1)
        if sub in ("特殊エネルギー", "基本エネルギー"):
            category = "Energy"
            trainer_subtype = "Special Energy" if sub == "特殊エネルギー" else "Basic Energy"
        else:
            category = "Trainer"
            trainer_subtype = TRAINER_SUBTYPES.get(sub, sub)

    # --- Abilities ---
    abilities = []
    ability_blocks = re.findall(
        r'<h2 class="mt20">特性</h2>\s*<h4>([^<]+)</h4>\s*<p>(.*?)</p>', right, re.DOTALL
    )
    for ab_name, ab_effect in ability_blocks:
        abilities.append({"name": ab_name.strip(), "effect": strip_tags(ab_effect)})

    # --- Attacks ---
    attacks = []
    waza_sections = re.findall(r'<h2 class="mt20">ワザ</h2>(.*?)(?=<h2 |$)', right, re.DOTALL)
    for waza_block in waza_sections:
        for am in re.finditer(r'<h4>(.*?)</h4>\s*(?:<p>(.*?)</p>)?', waza_block, re.DOTALL):
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
                num_m2 = re.match(r'^(\d+)', damage_str)
                if num_m2:
                    attack["damage"] = int(num_m2.group(1))
                    suffix = damage_str[num_m2.end():]
                    if suffix:
                        attack["damageModifier"] = suffix
                else:
                    attack["damageText"] = damage_str
            effect = strip_tags(effect_html).strip()
            if effect:
                attack["effect"] = effect
            attacks.append(attack)

    # --- Weakness / Resistance / Retreat ---
    weakness = None
    resistance = None
    retreat = 0
    table_m = re.search(r'<table[^>]*>(.*?)</table>', right, re.DOTALL)
    if table_m:
        tds = re.findall(r'<td[^>]*>(.*?)</td>', table_m.group(1), re.DOTALL)
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
            retreat = len(get_icons(rt))

    # --- Rarity: ex cards = Double Rare, others = Common ---
    # (M2a has no rarity icons on pokemon-card.com; base set has only C and RR)
    rarity = "Double Rare" if name.endswith("ex") else "Common"

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
        if dex_id:
            card["dexId"] = [dex_id]
        if description:
            card["description"] = description
        if evolve_from:
            card["evolveFrom"] = evolve_from
    else:
        if trainer_subtype:
            card["subcategory"] = trainer_subtype
        all_p = re.findall(r'<p>(.*?)</p>', right, re.DOTALL)
        effects = [strip_tags(p) for p in all_p if strip_tags(p)]
        if effects:
            card["effect"] = " ".join(effects)

    return card_num_str, card


def main():
    count = CARD_ID_END - CARD_ID_START + 1
    print(f"Fetching {count} M2a cards from pokemon-card.com...")
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
                print(f"  [{i:3d}/{count}] {card_id} → {num}: {card['name']} ({card['rarity']})")
            else:
                print(f"  [{i:3d}/{count}] {card_id} → FAILED")

    sorted_cards = dict(sorted(results.items()))

    data = {
        "id": SET_ID,
        "name": {"ja": SET_NAME},
        "serie": "M",
        "releaseDate": {"ja": "2025-11-28"},
        "cards": sorted_cards,
    }

    out_path = "data/M2a.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nDone! Wrote {len(sorted_cards)} cards to {out_path}")

    from collections import Counter
    cats = Counter(c["category"] for c in sorted_cards.values())
    rarities = Counter(c["rarity"] for c in sorted_cards.values())
    print("Category:", dict(cats))
    print("Rarity:", dict(rarities))


if __name__ == "__main__":
    main()
