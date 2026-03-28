#!/usr/bin/env python3
"""
Generate tcgdex TypeScript files for M2a (MEGAドリームex):
  data-asia/M/M2a.ts
  data-asia/M/M2a/001.ts … 193.ts

Usage:
  python3 scripts/generate_tcgdex_m2a.py /path/to/cards-database
"""

import json
import os
import sys

RARITY_MAP = {
    "Common":                    "Common",
    "Uncommon":                  "Uncommon",
    "Rare":                      "Rare",
    "Double Rare":               "Double rare",
    "Illustration Rare":         "Illustration rare",
    "Special Illustration Rare": "Special illustration rare",
    "Hyper Rare":                "Hyper rare",
    "Mega Hyper Rare":           "Mega hyper rare",
    "Unknown":                   "Unknown",
}

HOLO_RARITIES = {
    "Rare", "Double Rare", "Double rare",
    "Illustration Rare", "Illustration rare",
    "Special Illustration Rare", "Special illustration rare",
    "Hyper Rare", "Hyper rare",
    "Mega Hyper Rare", "Mega hyper rare",
}


def rarity_label(raw: str) -> str:
    return RARITY_MAP.get(raw, raw)


def is_holo(raw: str) -> bool:
    return raw in HOLO_RARITIES or rarity_label(raw) in HOLO_RARITIES


def js_string(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def damage_value(attack: dict):
    if "damageModifier" in attack:
        return f'"{attack["damage"]}{attack["damageModifier"]}"'
    if "damageText" in attack:
        return f'"{attack["damageText"]}"'
    if "damage" in attack:
        return str(attack["damage"])
    return None


def gen_set_file(outdir: str):
    content = '''import { Set } from "../../interfaces";
import serie from "../M";

const set: Set = {
\tid: "M2a",
\tname: {
\t\tja: "MEGAドリームex",
\t},

\tserie: serie,

\tcardCount: {
\t\tofficial: 193,
\t},
\treleaseDate: {
\t\tja: "2025-11-28",
\t},
};

export default set;
'''
    path = os.path.join(outdir, "M2a.ts")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Wrote {path}")


def gen_card_file(num_str: str, card: dict, outdir: str):
    lines = []
    lines.append('import { Card } from "../../../interfaces";')
    lines.append('import Set from "../M2a";')
    lines.append("")
    lines.append("const card: Card = {")
    lines.append("\tset: Set,")
    lines.append("\tname: {")
    lines.append(f'\t\tja: "{js_string(card["name"])}",')
    lines.append("\t},")
    lines.append("")

    illustrator = card.get("illustrator", "")
    lines.append(f'\tillustrator: "{js_string(illustrator)}",')
    lines.append(f'\tcategory: "{card["category"]}",')

    if card["category"] == "Pokemon":
        if "hp" in card:
            lines.append(f'\thp: {card["hp"]},')
        if card.get("types"):
            types_str = ", ".join(f'"{t}"' for t in card["types"])
            lines.append(f'\ttypes: [{types_str}],')
        lines.append("")
        desc = card.get("description", "")
        lines.append("\tdescription: {")
        lines.append(f'\t\tja: "{js_string(desc)}",')
        lines.append("\t},")
        lines.append("")

        stage = card.get("stage", "Basic")
        lines.append(f'\tstage: "{stage}",')

        if card.get("abilities"):
            lines.append("")
            ab_parts = []
            for ab in card["abilities"]:
                ab_parts.append(
                    '{"type": "Ability", '
                    + f'"name": {{"ja": "{js_string(ab["name"])}"}}, '
                    + f'"effect": {{"ja": "{js_string(ab.get("effect",""))}"}}' + "}"
                )
            lines.append(f'\tabilities: [{", ".join(ab_parts)}],')

        if card.get("attacks"):
            lines.append("")
            atk_parts = []
            for atk in card["attacks"]:
                parts = [f'"name": {{"ja": "{js_string(atk["name"])}"}}']
                if "cost" in atk:
                    cost_str = ", ".join(f'"{c}"' for c in atk["cost"])
                    parts.append(f'"cost": [{cost_str}]')
                dmg = damage_value(atk)
                if dmg is not None:
                    parts.append(f'"damage": {dmg}')
                if atk.get("effect"):
                    parts.append(f'"effect": {{"ja": "{js_string(atk["effect"])}"}}')
                atk_parts.append("{" + ", ".join(parts) + "}")
            lines.append(f'\tattacks: [{", ".join(atk_parts)}],')

        lines.append("")
        wk = card.get("weakness")
        if wk:
            lines.append(f'\tweaknesses: [{{"type": "{wk["type"]}", "value": "{wk["value"]}"}}],')
        else:
            lines.append("\tweaknesses: [],")
        rs = card.get("resistance")
        if rs:
            lines.append(f'\tresistances: [{{"type": "{rs["type"]}", "value": "{rs["value"]}"}}],')
        else:
            lines.append("\tresistances: [],")

        lines.append("")
        rarity_raw = card.get("rarity", "Common")
        variant_type = "holo" if is_holo(rarity_raw) else "normal"
        lines.append(f'\tvariants: [{{"type": "{variant_type}"}}],')

        evolve = card.get("evolveFrom")
        if evolve:
            lines.append("")
            lines.append("\tevolveFrom: {")
            lines.append(f'\t\tja: "{js_string(evolve)}",')
            lines.append("\t},")

        lines.append("")
        lines.append(f"\tretreat: {card.get('retreat', 0)},")
        lines.append('\tregulationMark: "I",')
        lines.append(f'\trarity: "{rarity_label(rarity_raw)}",')

        if card.get("dexId"):
            dex_str = ", ".join(str(d) for d in card["dexId"])
            lines.append(f"\tdexId: [{dex_str}],")

        if card["name"].endswith("ex"):
            lines.append('\tsuffix: "EX",')

    elif card["category"] == "Trainer":
        lines.append("")
        effect = card.get("effect", "")
        lines.append("\teffect: {")
        lines.append(f'\t\tja: "{js_string(effect)}",')
        lines.append("\t},")
        lines.append("")
        rarity_raw = card.get("rarity", "Common")
        variant_type = "holo" if is_holo(rarity_raw) else "normal"
        lines.append(f'\tvariants: [{{"type": "{variant_type}"}}],')
        lines.append("")
        subcategory = card.get("subcategory", "Item")
        lines.append(f'\ttrainerType: "{subcategory}",')
        lines.append('\tregulationMark: "I",')
        lines.append(f'\trarity: "{rarity_label(rarity_raw)}",')

    elif card["category"] == "Energy":
        lines.append("")
        effect = card.get("effect", "")
        lines.append("\teffect: {")
        lines.append(f'\t\tja: "{js_string(effect)}",')
        lines.append("\t},")
        lines.append("")
        rarity_raw = card.get("rarity", "Common")
        variant_type = "holo" if is_holo(rarity_raw) else "normal"
        lines.append(f'\tvariants: [{{"type": "{variant_type}"}}],')
        lines.append("")
        subcategory = card.get("subcategory", "Special Energy")
        if subcategory == "Special Energy":
            lines.append('\tenergyType: "Special",')
        lines.append('\tregulationMark: "I",')
        lines.append(f'\trarity: "{rarity_label(rarity_raw)}",')

    lines.append("};")
    lines.append("")
    lines.append("export default card;")
    lines.append("")

    card_dir = os.path.join(outdir, "M2a")
    os.makedirs(card_dir, exist_ok=True)
    path = os.path.join(card_dir, f"{num_str}.ts")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    if len(sys.argv) < 2:
        print("Usage: generate_tcgdex_m2a.py /path/to/cards-database")
        sys.exit(1)

    repo_dir = sys.argv[1]
    outdir = os.path.join(repo_dir, "data-asia", "M")

    with open("data/M2a.json", encoding="utf-8") as f:
        data = json.load(f)

    gen_set_file(outdir)

    cards = data["cards"]
    for num_str, card in sorted(cards.items()):
        gen_card_file(num_str, card, outdir)

    print(f"\nDone! Generated {len(cards)} card files + M2a.ts")

    from collections import Counter
    print("Rarity distribution:")
    for r, c in sorted(Counter(rarity_label(card["rarity"]) for card in cards.values()).items()):
        print(f"  {c:3d} {r}")


if __name__ == "__main__":
    main()
