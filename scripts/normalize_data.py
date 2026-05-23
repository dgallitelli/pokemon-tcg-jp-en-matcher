#!/usr/bin/env python3
"""
Normalize all sideload JSON files to a consistent schema.

Target schema (per ME4, the most complete file):
  Pokemon: name, id, set, image, category, hp, types, stage, retreat, dexId,
           rarity, illustrator, attacks[{name, damage?, cost?, effect?}],
           abilities?[{name, effect}], weakness?{type, value}, resistance?{type, value}
  Trainer: name, id, set, image, category, rarity, illustrator, effect, subcategory
  Energy:  name, id, set, image, category, rarity, effect, subcategory?

This script:
1. Backfills M4 from ME4 (weakness, resistance, abilities, attack costs/effects, trainer/energy data)
2. Backfills M3 from ME3 (attack costs — ME3 lacks weakness/resistance too)
3. Ensures structural consistency (empty arrays for missing attacks, etc.)
"""
import json, pathlib, copy

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"


def load(name):
    return json.loads((DATA / f"{name}.json").read_text())


def save(name, data):
    (DATA / f"{name}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"  Saved {name}.json")


def backfill_from_en(jp_data, en_data, jp_set_id, en_set_id):
    """Backfill JP cards from their EN translation counterpart."""
    jp_cards = jp_data["cards"]
    en_cards = en_data["cards"]
    stats = {"weakness": 0, "resistance": 0, "abilities": 0, "attack_cost": 0,
             "attack_effect": 0, "trainer_effect": 0, "subcategory": 0}

    # Build dexId → EN card lookup for secret rares that may not align by number
    en_by_dex = {}
    for num, ec in en_cards.items():
        for dex in ec.get("dexId", []):
            en_by_dex.setdefault(dex, []).append((num, ec))

    for num, jc in jp_cards.items():
        # Try matching by card number first, then by dexId+illustrator
        ec = en_cards.get(num)
        if not ec and jc.get("dexId"):
            candidates = en_by_dex.get(jc["dexId"][0], [])
            # Prefer illustrator match
            for _, c in candidates:
                if c.get("illustrator") and jc.get("illustrator") and \
                   c["illustrator"].lower() == jc["illustrator"].lower():
                    ec = c
                    break
            if not ec and candidates:
                ec = candidates[0][1]  # fallback to first dexId match

        if not ec:
            continue

        cat = jc.get("category", "")

        if cat == "Pokemon":
            # Weakness
            if "weakness" not in jc and "weakness" in ec:
                jc["weakness"] = copy.deepcopy(ec["weakness"])
                stats["weakness"] += 1
            # Resistance
            if "resistance" not in jc and "resistance" in ec:
                jc["resistance"] = copy.deepcopy(ec["resistance"])
                stats["resistance"] += 1
            # Abilities
            if "abilities" not in jc and "abilities" in ec:
                jc["abilities"] = copy.deepcopy(ec["abilities"])
                stats["abilities"] += 1
            # Attack costs and effects
            jp_atks = jc.get("attacks", [])
            en_atks = ec.get("attacks", [])
            if len(jp_atks) == len(en_atks):
                for ja, ea in zip(jp_atks, en_atks):
                    if "cost" not in ja and "cost" in ea:
                        ja["cost"] = copy.deepcopy(ea["cost"])
                        stats["attack_cost"] += 1
                    if "effect" not in ja and "effect" in ea:
                        ja["effect"] = ea["effect"]
                        stats["attack_effect"] += 1
            elif len(jp_atks) == 0 and len(en_atks) > 0:
                # JP has no attacks at all — copy structure from EN but keep JP names as-is
                # We can't copy names (different language), so just add cost/effect to stubs
                pass

        elif cat == "Trainer":
            if "effect" not in jc and "effect" in ec:
                jc["effect"] = ec["effect"]
                stats["trainer_effect"] += 1
            if "subcategory" not in jc and "subcategory" in ec:
                jc["subcategory"] = ec["subcategory"]
                stats["subcategory"] += 1

        elif cat == "Energy":
            if "effect" not in jc and "effect" in ec:
                jc["effect"] = ec["effect"]
                stats["trainer_effect"] += 1
            if "subcategory" not in jc and "subcategory" in ec:
                jc["subcategory"] = ec["subcategory"]
                stats["subcategory"] += 1

    return stats


def ensure_structural_consistency(data, set_id):
    """Ensure all cards have consistent field presence."""
    fixed = 0
    for num, card in data["cards"].items():
        cat = card.get("category", "")

        if cat == "Pokemon":
            # Ensure attacks is always a list (not missing)
            if "attacks" not in card:
                card["attacks"] = []
                fixed += 1
            # Ensure dexId is always a list
            if "dexId" not in card:
                card["dexId"] = []
                fixed += 1

        # Ensure id and set are always present
        if "id" not in card:
            card["id"] = f"{set_id}-{num}"
            fixed += 1
        if "set" not in card:
            card["set"] = {"id": set_id, "name": data.get("name", {}).get("ja") or data.get("name", {}).get("en", set_id)}
            fixed += 1
        if "image" not in card:
            card["image"] = None
            fixed += 1

    return fixed


def main():
    print("=== Normalizing sideload data ===\n")

    # 1. Backfill M4 from ME4
    print("1. Backfilling M4 from ME4...")
    m4 = load("M4")
    me4 = load("ME4")
    stats = backfill_from_en(m4, me4, "M4", "ME4")
    print(f"   Backfilled: {stats}")
    fixed = ensure_structural_consistency(m4, "M4")
    print(f"   Structural fixes: {fixed}")
    save("M4", m4)

    # 2. Backfill M3 from ME3
    print("\n2. Backfilling M3 from ME3...")
    m3 = load("M3")
    me3 = load("ME3")
    stats = backfill_from_en(m3, me3, "M3", "ME3")
    print(f"   Backfilled: {stats}")
    fixed = ensure_structural_consistency(m3, "M3")
    print(f"   Structural fixes: {fixed}")
    save("M3", m3)

    # 3. Structural consistency for M1S, M1L, M2, SV6a
    # SV6a is a JP sideload that pulls EN data live from TCGdex sv06.5 (no ME6a),
    # so it only needs structural normalization here, not a backfill step.
    for sid in ["M1S", "M1L", "M2", "SV6a"]:
        print(f"\n3. Ensuring structural consistency for {sid}...")
        d = load(sid)
        fixed = ensure_structural_consistency(d, sid)
        print(f"   Structural fixes: {fixed}")
        save(sid, d)

    # 4. Structural consistency for ME3
    print("\n4. Ensuring structural consistency for ME3...")
    me3 = load("ME3")
    fixed = ensure_structural_consistency(me3, "ME3")
    print(f"   Structural fixes: {fixed}")
    save("ME3", me3)

    # Final audit
    print("\n=== Post-normalization audit ===")
    for f in ["M1S", "M1L", "M2", "M3", "M4", "ME3", "ME4", "SV6a"]:
        d = load(f)
        cards = d["cards"]
        poke = [c for c in cards.values() if c.get("category") == "Pokemon"]
        train = [c for c in cards.values() if c.get("category") == "Trainer"]
        ener = [c for c in cards.values() if c.get("category") == "Energy"]
        has_w = sum(1 for c in poke if "weakness" in c)
        has_r = sum(1 for c in poke if "resistance" in c)
        has_abil = sum(1 for c in poke if "abilities" in c)
        has_cost = sum(1 for c in poke if any("cost" in a for a in c.get("attacks", [])))
        has_eff = sum(1 for c in poke if any("effect" in a for a in c.get("attacks", [])))
        empty = sum(1 for c in poke if len(c.get("attacks", [])) == 0)
        tr_eff = sum(1 for c in train if "effect" in c)
        subcat = sum(1 for c in train if "subcategory" in c)
        en_eff = sum(1 for c in ener if "effect" in c)
        print(f"  {f}: {len(poke)}P weak:{has_w} res:{has_r} abil:{has_abil} cost:{has_cost} eff:{has_eff} empty_atk:{empty} | {len(train)}T eff:{tr_eff} sub:{subcat} | {len(ener)}E eff:{en_eff}")


if __name__ == "__main__":
    main()
