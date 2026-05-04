#!/usr/bin/env python3
"""
Build data/ME2a.json from TCGdex's Destined Rivals set (sv10).

M2a (MEGA Dream ex) is the Japanese counterpart of Destined Rivals (sv10).
This script replaces the previous best-effort ME2a.json (machine-translated
from the Japanese via Serebii) with authoritative TCGdex English data.

Usage:
  python3 scripts/build_me2a_from_tcgdex.py
"""
import json
import pathlib
import sys
import urllib.request
import urllib.error

API = "https://api.tcgdex.net/v2/en"
SET_ID = "sv10"
OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "ME2a.json"


def fetch(path):
    with urllib.request.urlopen(f"{API}/{path}", timeout=30) as r:
        return json.load(r)


def simplify_card(full, me2a_num):
    """Translate TCGdex card shape into our ME2a sideload shape."""
    # TCGdex image field is like "https://assets.tcgdex.net/en/sv/sv10/003"
    # renderCard appends "/high.webp" for paths without an extension
    image = full.get("image")
    out = {
        "name": full["name"],
        "id": f"ME2a-{me2a_num}",
        "set": {"id": "ME2a", "name": "MEGA Dream ex"},
        "image": image,
        "category": full.get("category", "Pokemon"),
    }
    if full.get("illustrator"):
        out["illustrator"] = full["illustrator"]
    if full.get("rarity"):
        out["rarity"] = full["rarity"]
    if out["category"] == "Pokemon":
        if full.get("hp"):
            out["hp"] = full["hp"]
        if full.get("types"):
            out["types"] = full["types"]
        if full.get("stage"):
            out["stage"] = full["stage"]
        if full.get("evolveFrom"):
            out["evolveFrom"] = full["evolveFrom"]
        if full.get("dexId"):
            out["dexId"] = full["dexId"]
        if full.get("abilities"):
            out["abilities"] = [
                {"name": a["name"], "effect": a.get("effect", ""), "type": a.get("type", "Ability")}
                for a in full["abilities"]
            ]
        if full.get("attacks"):
            atks = []
            for a in full["attacks"]:
                atk = {"name": a["name"]}
                if a.get("cost"):
                    atk["cost"] = a["cost"]
                if a.get("damage") is not None:
                    atk["damage"] = a["damage"]
                if a.get("effect"):
                    atk["effect"] = a["effect"]
                atks.append(atk)
            out["attacks"] = atks
        # Weakness — TCGdex uses "weaknesses" (array), we use single "weakness"
        ws = full.get("weaknesses") or []
        if ws:
            out["weakness"] = {"type": ws[0]["type"], "value": ws[0].get("value", "x2")}
        rs = full.get("resistances") or []
        if rs:
            out["resistance"] = {"type": rs[0]["type"], "value": rs[0].get("value", "-30")}
        if full.get("retreat") is not None:
            out["retreat"] = full["retreat"]
        if full.get("description"):
            out["description"] = full["description"]
    elif out["category"] in ("Trainer", "Energy"):
        if full.get("effect"):
            out["effect"] = full["effect"]
        if full.get("trainerType"):
            out["subcategory"] = full["trainerType"]
        if full.get("energyType"):
            out["subcategory"] = full["energyType"]
    return out


def main():
    print(f"Fetching set {SET_ID} from TCGdex...", file=sys.stderr)
    set_data = fetch(f"sets/{SET_ID}")
    cards_summary = set_data.get("cards", [])
    print(f"  Found {len(cards_summary)} cards in {set_data.get('name')}", file=sys.stderr)

    cards = {}
    for i, c in enumerate(cards_summary, 1):
        local_id = c.get("localId") or c.get("id", "").split("-")[-1]
        # Pad to 3 digits to match our M2a numbering
        key = str(int(local_id)).zfill(3) if str(local_id).isdigit() else local_id
        print(f"  [{i}/{len(cards_summary)}] {c['id']} {c['name']}", file=sys.stderr)
        try:
            full = fetch(f"cards/{c['id']}")
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            print(f"    skip: {e}", file=sys.stderr)
            continue
        cards[key] = simplify_card(full, key)

    out = {
        "id": "ME2a",
        "name": "MEGA Dream ex",
        "serie": "Mega Evolution",
        "releaseDate": {"en": set_data.get("releaseDate") or "2026-05-30"},
        "jpSetId": "M2a",
        "tcgdexSetId": SET_ID,
        "cards": cards,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(cards)} cards to {OUT}")


if __name__ == "__main__":
    main()
