#!/usr/bin/env python3
"""Fix remaining data gaps that the scraper missed."""
import json, pathlib

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"


def load(name):
    return json.loads((DATA / f"{name}.json").read_text())


def save(name, data):
    (DATA / f"{name}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def patch_card(data, num, **fields):
    if num in data["cards"]:
        data["cards"][num].update(fields)
        return True
    return False


# --- M1L fixes ---
m1l = load("M1L")
patch_card(m1l, "060", effect="Provides 1 Colorless Energy.", subcategory="Special Energy")
patch_card(m1l, "063",
    effect="This card stays in play when you play it. Discard this card if another Stadium card comes into play. If another card with the same name is in play, you can't play this card.",
    subcategory="Stadium")
save("M1L", m1l)
print("Fixed M1L: 060 (energy), 063 (stadium)")

# --- M2 fixes ---
m2 = load("M2")
patch_card(m2, "075",
    effect="The Pokémon this card is attached to takes 30 less damage from attacks by your opponent's Pokémon that have Abilities.",
    subcategory="Pokemon Tool")
patch_card(m2, "103",
    effect="The Pokémon this card is attached to takes 30 less damage from attacks by your opponent's Pokémon that have Abilities.",
    subcategory="Pokemon Tool")
patch_card(m2, "104",
    effect="If the Darkness Pokémon this card is attached to is in the Active Spot and is damaged by an attack from your opponent's Pokémon (even if it is Knocked Out), put 4 damage counters on the Attacking Pokémon.",
    subcategory="Pokemon Tool")
patch_card(m2, "109",
    effect="Discard this card at the end of the turn it was attached. Provides 1 Colorless Energy. If attached to an Evolution Pokémon, provides 3 Colorless Energy instead.",
    subcategory="Special Energy")
save("M2", m2)
print("Fixed M2: 075, 103 (Sacred Charm), 104 (Punk Helmet), 109 (Ignition Energy)")

# --- M4 energy subcategory ---
m4 = load("M4")
for num in ["081", "082", "083"]:
    if num in m4["cards"] and m4["cards"][num].get("category") == "Energy":
        m4["cards"][num].setdefault("subcategory", "Special Energy")
# Also fix any remaining M4 trainers missing subcategory from ME4 backfill
me4 = load("ME4")
for num, ec in me4["cards"].items():
    if num in m4["cards"] and ec.get("subcategory"):
        m4["cards"][num].setdefault("subcategory", ec["subcategory"])
save("M4", m4)
print("Fixed M4: energy subcategories + trainer subcategories from ME4")

# --- ME4 energy subcategory ---
me4_data = load("ME4")
for num, card in me4_data["cards"].items():
    if card.get("category") == "Energy":
        card.setdefault("subcategory", "Special Energy")
save("ME4", me4_data)
print("Fixed ME4: energy subcategories")

# --- M3 energy subcategory ---
m3 = load("M3")
for num, card in m3["cards"].items():
    if card.get("category") == "Energy":
        card.setdefault("subcategory", "Special Energy")
save("M3", m3)
print("Fixed M3: energy subcategories")

# --- ME3 energy subcategory ---
me3 = load("ME3")
for num, card in me3["cards"].items():
    if card.get("category") == "Energy":
        card.setdefault("subcategory", "Special Energy")
save("ME3", me3)
print("Fixed ME3: energy subcategories")

print("\nDone!")
