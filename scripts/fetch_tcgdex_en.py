#!/usr/bin/env python3
"""
Fetch EN card data from tcgdex API for Mega Evolution sets and:
1. Create ME1.json and ME2.json sideload files
2. Backfill missing attack costs/effects to M1S, M1L, M2 JP sets
"""
import json, pathlib, time, sys
from urllib.request import urlopen, Request

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
API = "https://api.tcgdex.net/v2/en"


def api_get(path):
    url = f"{API}/{path}"
    req = Request(url, headers={"User-Agent": "Pokemon TCG JP-EN Matcher"})
    for attempt in range(3):
        try:
            with urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except Exception as e:
            if attempt < 2:
                time.sleep(1)
            else:
                print(f"  FAILED: {url} — {e}")
                return None


def fetch_set_cards(set_id):
    """Fetch all cards in a set from tcgdex API."""
    set_data = api_get(f"sets/{set_id}")
    if not set_data:
        return {}

    cards = {}
    card_list = set_data.get("cards", [])
    print(f"  Fetching {len(card_list)} cards from {set_id}...")

    for i, card_stub in enumerate(card_list):
        card_id = card_stub["id"]
        card = api_get(f"cards/{card_id}")
        if not card:
            continue

        local_id = card.get("localId", "")
        entry = {"name": card.get("name", "")}

        if card.get("illustrator"):
            entry["illustrator"] = card["illustrator"]
        if card.get("rarity"):
            entry["rarity"] = card["rarity"]
        if card.get("category"):
            entry["category"] = card["category"]
        if card.get("hp"):
            entry["hp"] = card["hp"]
        if card.get("types"):
            entry["types"] = card["types"]
        if card.get("stage"):
            entry["stage"] = card["stage"]
        if card.get("dexId"):
            entry["dexId"] = card["dexId"]
        if card.get("evolveFrom"):
            entry["evolveFrom"] = card["evolveFrom"]

        # Attacks
        if card.get("attacks"):
            attacks = []
            for atk in card["attacks"]:
                a = {"name": atk.get("name", "")}
                if atk.get("cost"):
                    a["cost"] = atk["cost"]
                if atk.get("damage") is not None:
                    a["damage"] = atk["damage"]
                if atk.get("effect"):
                    a["effect"] = atk["effect"]
                attacks.append(a)
            entry["attacks"] = attacks

        # Abilities
        if card.get("abilities"):
            abilities = []
            for ab in card["abilities"]:
                a = {"name": ab.get("name", "")}
                if ab.get("effect"):
                    a["effect"] = ab["effect"]
                if ab.get("type"):
                    a["type"] = ab["type"]
                abilities.append(a)
            entry["abilities"] = abilities

        # Defense
        if card.get("weaknesses"):
            w = card["weaknesses"][0]
            entry["weakness"] = {"type": w.get("type", ""), "value": w.get("value", "x2")}
        if card.get("resistances"):
            r = card["resistances"][0]
            entry["resistance"] = {"type": r.get("type", ""), "value": r.get("value", "-30")}
        if card.get("retreat") is not None:
            entry["retreat"] = card["retreat"]

        # Trainer/Energy
        if card.get("effect"):
            entry["effect"] = card["effect"]
        if card.get("trainerType"):
            entry["subcategory"] = card["trainerType"]
        if card.get("energyType"):
            entry["energyType"] = card["energyType"]
        if card.get("suffix"):
            entry["suffix"] = card["suffix"]

        cards[local_id] = entry

        if (i + 1) % 20 == 0:
            print(f"    {i + 1}/{len(card_list)} fetched...")
        time.sleep(0.15)  # Be polite to API

    return cards


def save_sideload(name, en_name, cards):
    """Save a sideload JSON file."""
    data = {"name": en_name, "cards": cards}
    path = DATA / f"{name}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"  Saved {path.name}: {len(cards)} cards")


def match_and_backfill(jp_set_name, en_cards):
    """Match EN cards to JP set by dexId+illustrator and backfill attack data."""
    jp_path = DATA / f"{jp_set_name}.json"
    if not jp_path.exists():
        return

    jp_data = json.loads(jp_path.read_text())
    jp_cards = jp_data["cards"]

    # Build EN index by dexId
    en_by_dex = {}
    for num, ec in en_cards.items():
        for did in ec.get("dexId", []):
            en_by_dex.setdefault(did, []).append(ec)

    stats = {"cost_filled": 0, "effect_filled": 0, "ability_filled": 0}

    for num, jc in jp_cards.items():
        if jc.get("category") != "Pokemon":
            continue

        # Find matching EN card by dexId + illustrator
        candidates = []
        for did in jc.get("dexId", []):
            candidates.extend(en_by_dex.get(did, []))

        if not candidates:
            continue

        # Prefer illustrator match
        match = None
        for ec in candidates:
            if ec.get("illustrator") == jc.get("illustrator"):
                match = ec
                break
        if not match:
            # Fall back to HP match
            for ec in candidates:
                if ec.get("hp") == jc.get("hp"):
                    match = ec
                    break
        if not match:
            match = candidates[0]

        # Backfill attacks
        jp_attacks = jc.get("attacks", [])
        en_attacks = match.get("attacks", [])

        if len(jp_attacks) == len(en_attacks):
            for ja, ea in zip(jp_attacks, en_attacks):
                if "cost" not in ja and "cost" in ea:
                    ja["cost"] = ea["cost"]
                    stats["cost_filled"] += 1
                if "effect" not in ja and "effect" in ea:
                    ja["effect"] = ea["effect"]
                    stats["effect_filled"] += 1

        # Backfill abilities
        if "abilities" not in jc and "abilities" in match:
            jc["abilities"] = match["abilities"]
            stats["ability_filled"] += 1

        # Backfill weakness/resistance
        if "weakness" not in jc and "weakness" in match:
            jc["weakness"] = match["weakness"]
        if "resistance" not in jc and "resistance" in match:
            jc["resistance"] = match["resistance"]

    jp_path.write_text(json.dumps(jp_data, indent=2, ensure_ascii=False) + "\n")
    print(f"  Backfilled {jp_set_name}: cost={stats['cost_filled']} effect={stats['effect_filled']} ability={stats['ability_filled']}")


def backfill_sv6a_from_sv065(en_cards):
    """Backfill SV6a JP cards from sv06.5 (Shrouded Fable) EN cards.

    SV6a's main set #1–64 mirrors sv06.5 #1–64 1:1 by collector number, so we
    match by number for those and by JP→EN name for secret rares (#65–94).
    Unlike match_and_backfill (which requires the JP card to already have a
    dexId), this function *populates* dexId on JP cards from the EN match —
    that's the missing field that lets the app.js matcher find the EN card
    via its TCGdex EN dexId path.
    """
    jp_path = DATA / "SV6a.json"
    if not jp_path.exists():
        print("  SV6a.json not found — run scripts/scrape_sv6a.py first")
        return

    jp_data = json.loads(jp_path.read_text())
    jp_cards = jp_data["cards"]

    # JP→EN Pokemon name map for secret-rare resolution. Mirror of POKEMON_NAME_MAP
    # in app.js (the subset relevant to SV6a/sv06.5). Keep this small and audited.
    JP_TO_EN_NAME = {
        "カプ・ブルル": "Tapu Bulu", "ヘルガー": "Houndoom", "タッツー": "Horsea",
        "ヨマワル": "Duskull", "サマヨール": "Dusclops", "ヨノワール": "Dusknoir",
        "クレセリア": "Cresselia", "ゾロア": "Zorua", "ゾウドウ": "Cufant",
        "オノンド": "Axew", "ペルシアン": "Persian", "キテルグマ": "Bewear",
        "ブロロローム": "Revavroom", "キングドラ": "Kingdra",
        "イイネイヌ": "Okidogi", "マシマシラ": "Munkidori",
        "キチキギス": "Fezandipiti", "モモワロウ": "Pecharunt",
    }

    def base_name(s):
        """Strip trailing ' ex' suffix from EN names so 'Kingdra ex' indexes under 'kingdra'."""
        s = (s or "").lower().strip()
        return s[:-3].rstrip() if s.endswith(" ex") else s

    en_by_num = {ec_num: ec for ec_num, ec in en_cards.items()}
    en_by_basename = {}
    for ec in en_cards.values():
        en_by_basename.setdefault(base_name(ec.get("name", "")), []).append(ec)

    stats = {"dex_filled": 0, "weak_filled": 0, "res_filled": 0,
             "abil_filled": 0, "cost_filled": 0, "effect_filled": 0,
             "trainer_eff_filled": 0, "missed": 0}

    for num, jc in jp_cards.items():
        match = None
        n = int(num)

        # #1–64: positional 1:1 match against sv06.5
        if n <= 64:
            match = en_by_num.get(num)

        # #65–94 (or fallback): name-based match
        if not match:
            jp_name = jc.get("name", "")
            is_ex = jp_name.endswith("ex")
            bare = jp_name[:-2].rstrip() if is_ex else jp_name
            en_name = JP_TO_EN_NAME.get(bare)
            if en_name:
                cands = en_by_basename.get(en_name.lower(), [])
                # Match ex-ness — JP "Xex" → EN "X ex", JP "X" → EN "X"
                cands = [c for c in cands if c.get("name", "").lower().endswith(" ex") == is_ex]
                # Prefer illustrator match when multiple remain
                if jc.get("illustrator") and len(cands) > 1:
                    illus_match = [c for c in cands if c.get("illustrator") == jc.get("illustrator")]
                    if illus_match:
                        cands = illus_match
                if cands:
                    match = cands[0]

        if not match:
            stats["missed"] += 1
            continue

        cat = jc.get("category", "")

        if cat == "Pokemon":
            # Populate dexId — the key thing that lets the matcher find sv06.5 cards
            if "dexId" not in jc and "dexId" in match:
                jc["dexId"] = match["dexId"]
                stats["dex_filled"] += 1
            # Backfill weakness / resistance / abilities (Serebii data may be stale)
            if "weakness" not in jc and "weakness" in match:
                jc["weakness"] = match["weakness"]
                stats["weak_filled"] += 1
            if "resistance" not in jc and "resistance" in match:
                jc["resistance"] = match["resistance"]
                stats["res_filled"] += 1
            if "abilities" not in jc and "abilities" in match:
                jc["abilities"] = match["abilities"]
                stats["abil_filled"] += 1
            # Backfill attack cost/effect when count matches
            jp_atks = jc.get("attacks", [])
            en_atks = match.get("attacks", [])
            if len(jp_atks) == len(en_atks):
                for ja, ea in zip(jp_atks, en_atks):
                    if "cost" not in ja and "cost" in ea:
                        ja["cost"] = ea["cost"]
                        stats["cost_filled"] += 1
                    if "effect" not in ja and "effect" in ea:
                        ja["effect"] = ea["effect"]
                        stats["effect_filled"] += 1
        elif cat in ("Trainer", "Energy"):
            if "effect" not in jc and "effect" in match:
                jc["effect"] = match["effect"]
                stats["trainer_eff_filled"] += 1
            if "subcategory" not in jc and "subcategory" in match:
                jc["subcategory"] = match["subcategory"]

    jp_path.write_text(json.dumps(jp_data, indent=2, ensure_ascii=False) + "\n")
    print(f"  Backfilled SV6a: {stats}")


if __name__ == "__main__":
    import sys
    only = sys.argv[1] if len(sys.argv) > 1 else None

    if not only or only == "ME01":
        # Fetch ME01 (Mega Evolution = EN of M1S + M1L)
        print("=== Fetching ME01 (Mega Evolution) ===")
        me01_cards = fetch_set_cards("me01")
        if me01_cards:
            save_sideload("ME1", "Mega Evolution", me01_cards)
            print("  Backfilling M1S...")
            match_and_backfill("M1S", me01_cards)
            print("  Backfilling M1L...")
            match_and_backfill("M1L", me01_cards)

    if not only or only == "ME02":
        # Fetch ME02 (Phantasmal Flames = EN of M2)
        print("\n=== Fetching ME02 (Phantasmal Flames) ===")
        me02_cards = fetch_set_cards("me02")
        if me02_cards:
            save_sideload("ME2", "Phantasmal Flames", me02_cards)
            print("  Backfilling M2...")
            match_and_backfill("M2", me02_cards)

    if not only or only == "SV6a":
        # Backfill SV6a from sv06.5 (Shrouded Fable) — no save_sideload, no ME6a file.
        # SV6a's EN counterpart already lives in TCGdex live data; we only need to
        # populate dexId + verify field consistency on the JP cards.
        print("\n=== Backfilling SV6a from sv06.5 (Shrouded Fable) ===")
        sv065_cards = fetch_set_cards("sv06.5")
        if sv065_cards:
            backfill_sv6a_from_sv065(sv065_cards)

    print("\nDone!")
