#!/usr/bin/env python3
"""
Generate tcgdex TypeScript files for M4 (Ninja Spinner):
  data-asia/M/M4.ts
  data-asia/M/M4/001.ts … 120.ts

Usage:
  python3 scripts/generate_tcgdex_m4.py /path/to/cards-database
"""

import json
import os
import sys

# ── Rarity → tcgdex label ────────────────────────────────────────────────────
RARITY_MAP = {
    "Common":                    "Common",
    "Uncommon":                  "Uncommon",
    "Rare":                      "Rare",
    "Double Rare":               "Double rare",
    "Illustration Rare":         "Illustration rare",
    "Special Illustration Rare": "Special illustration rare",
    "Hyper Rare":                "Hyper rare",
    "Mega Hyper Rare":           "Mega hyper rare",
    "Mega Art Rare":             "Mega art rare",
    "Unknown":                   "Unknown",
}

# ── Rarity → variants ────────────────────────────────────────────────────────
HOLO_RARITIES = {
    "Rare", "Double Rare", "Double rare",
    "Illustration Rare", "Illustration rare",
    "Special Illustration Rare", "Special illustration rare",
    "Hyper Rare", "Hyper rare",
    "Mega Hyper Rare", "Mega hyper rare",
    "Mega Art Rare", "Mega art rare",
}

# ── Evolution chains (JP name → evolves from JP name) ────────────────────────
EVOLVE_FROM = {
    # Line 1: Caterpie
    "コクーン":        "ビードル",
    "スピアーex":      "コクーン",
    # Line 2: Chespin
    "ハリボーグ":      "ハリマロン",
    "ブリガロン":      "ハリボーグ",
    # Line 3: Vulpix
    "キュウコン":      "ロコン",
    # Line 4: Fennekin
    "テールナー":      "フォッコ",
    "マフォクシー":    "テールナー",
    # Line 5: Litleo
    "メガカエンジシex": "シシコ",
    # Line 6: Remoraid
    "オクタン":        "テッポウオ",
    # Line 7: Froakie
    "ゲコガシラ":      "ケロマツ",
    "メガゲッコウガex": "ゲコガシラ",
    # Line 8: Bergmite
    "クレベース":      "カチコール",
    # Line 9: Dewpider
    "グソクムシャ":    "コソクムシ",
    # Line 10: Mareep
    "モココ":          "メリープ",
    "デンリュウ":      "モココ",
    # Line 11: Espurr
    "ニャオニクス":    "ニャスパー",
    # Line 12: Phantump
    "オーロット":      "ボクレー",
    # Line 13: Pumpkaboo
    "パンプジンex":    "バケッチャ",
    # Line 14: Phanpy
    "ドンファン":      "ゴマゾウ",
    # Line 15: Baltoy
    "ネンドール":      "ヤジロン",
    # Line 16: Zubat
    "ゴルバット":      "ズバット",
    "クロバット":      "ゴルバット",
    # Line 17: Skuntank
    "スカタンク":      "スカンプー",
    # Line 18: Trubbish
    "ダストダス":      "ヤブクロン",
    # Line 19: Beldum
    "メタング":        "ダンバル",
    "メタグロス":      "メタング",
    # Line 20: Ferroseed
    "ナットレイ":      "テッシード",
    # Line 21: Skrelp (evolves directly since Dragalge not in set)
    "メガドラミドロex": "クズモー",
    # Line 22: Goomy
    "ヌメイル":        "ヌメラ",
    "ヌメルゴン":      "ヌメイル",
    # Line 23: Minccino
    "ミルホッグ":      "ミネズミ",
    # Line 24: Cinccino
    "チラチーノex":    "チラーミィ",
}


def rarity_label(raw: str) -> str:
    return RARITY_MAP.get(raw, raw)


def is_holo(raw: str) -> bool:
    return raw in HOLO_RARITIES or rarity_label(raw) in HOLO_RARITIES


def js_string(s: str) -> str:
    """Escape a string for use in JS/TS."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def damage_value(attack: dict):
    """Return damage as string (if modifier) or int."""
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
\tid: "M4",
\tname: {
\t\tja: "Ninja Spinner",
\t},

\tserie: serie,

\tcardCount: {
\t\tofficial: 120,
\t},
\treleaseDate: {
\t\tja: "2026-03-13",
\t},
};

export default set;
'''
    path = os.path.join(outdir, "M4.ts")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Wrote {path}")


def gen_card_file(num_str: str, card: dict, outdir: str):
    lines = []
    lines.append('import { Card } from "../../../interfaces";')
    lines.append('import Set from "../M4";')
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
        # Description (blank for ex, empty string default)
        lines.append("\tdescription: {")
        lines.append('\t\tja: "",')
        lines.append("\t},")
        lines.append("")

        stage = card.get("stage", "Basic")
        lines.append(f'\tstage: "{stage}",')

        if card.get("abilities"):
            lines.append("")
            ab_parts = []
            for ab in card["abilities"]:
                ab_parts.append(
                    '{' +
                    '"type": "Ability", ' +
                    f'"name": {{"ja": "{js_string(ab["name"])}"}}, ' +
                    f'"effect": {{"ja": "{js_string(ab.get("effect",""))}"}}'
                    + '}'
                )
            lines.append(f'\tabilities: [{", ".join(ab_parts)}],')

        if card.get("attacks"):
            lines.append("")
            atk_parts = []
            for atk in card["attacks"]:
                parts = []
                parts.append(f'"name": {{"ja": "{js_string(atk["name"])}"}}')
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
        # Weakness
        wk = card.get("weakness")
        if wk:
            lines.append(f'\tweaknesses: [{{"type": "{wk["type"]}", "value": "{wk["value"]}"}}],')
        else:
            lines.append("\tweaknesses: [],")
        # Resistance
        rs = card.get("resistance")
        if rs:
            lines.append(f'\tresistances: [{{"type": "{rs["type"]}", "value": "{rs["value"]}"}}],')
        else:
            lines.append("\tresistances: [],")

        lines.append("")
        rarity_raw = card.get("rarity", "Common")
        holo = is_holo(rarity_raw)
        variant_type = "holo" if holo else "normal"
        lines.append(f'\tvariants: [{{"type": "{variant_type}"}}],')

        # evolveFrom
        evolve = EVOLVE_FROM.get(card["name"])
        if evolve:
            lines.append("")
            lines.append("\tevolveFrom: {")
            lines.append(f'\t\tja: "{js_string(evolve)}",')
            lines.append("\t},")

        lines.append("")
        retreat = card.get("retreat", 0)
        lines.append(f"\tretreat: {retreat},")
        lines.append('\tregulationMark: "I",')
        lines.append(f'\trarity: "{rarity_label(rarity_raw)}",')

        if card.get("dexId"):
            dex_str = ", ".join(str(d) for d in card["dexId"])
            lines.append(f"\tdexId: [{dex_str}],")

        # suffix for ex Pokémon
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
        holo = is_holo(rarity_raw)
        variant_type = "holo" if holo else "normal"
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
        holo = is_holo(rarity_raw)
        variant_type = "holo" if holo else "normal"
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

    card_dir = os.path.join(outdir, "M4")
    os.makedirs(card_dir, exist_ok=True)
    path = os.path.join(card_dir, f"{num_str}.ts")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    if len(sys.argv) < 2:
        print("Usage: generate_tcgdex_m4.py /path/to/cards-database")
        sys.exit(1)

    repo_dir = sys.argv[1]
    outdir = os.path.join(repo_dir, "data-asia", "M")

    with open("data/M4.json", encoding="utf-8") as f:
        data = json.load(f)

    gen_set_file(outdir)

    cards = data["cards"]
    for num_str, card in sorted(cards.items()):
        gen_card_file(num_str, card, outdir)
        print(f"  {num_str}: {card['name']}")

    print(f"\nDone! Generated {len(cards)} card files + M4.ts")


if __name__ == "__main__":
    main()
