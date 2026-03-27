#!/usr/bin/env python3
"""
Enrich M3.json and ME3.json with abilities, attack effects, and trainer effects.

Card translations sourced from PokeBeach (Jake C. translations) for the
Nihil Zero / Perfect Order set.

This script:
1. Reads existing M3.json and ME3.json
2. Patches in abilities and attack effects from the PokeBeach translations
3. Writes enriched versions back
"""
import json, pathlib, copy

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
M3_PATH = DATA / "M3.json"
ME3_PATH = DATA / "ME3.json"

# PokeBeach translations for the 80 main set cards + trainers/energy
# Format: card_num -> { abilities: [...], attacks: [{name, effect}], effect (for trainers) }
# We only store the ENRICHMENT data — name/hp/etc already exist in the files.

ENRICHMENTS = {
    # --- Grass ---
    "001": {  # Spinarak
        "attacks": [{"name_en": "Gooey Thread", "effect": "During your opponent's next turn, the Defending Pokemon can't retreat."}],
    },
    "002": {  # Ariados
        "attacks": [{"name_en": "Poison Circle", "effect": "Your opponent's Active Pokemon is now Poisoned. During your opponent's next turn, the Defending Pokemon can't retreat."}],
    },
    "003": {  # Shaymin
        "attacks": [
            {"name_en": "Flower Delivery", "effect": "Search your deck for an Energy and attach it to 1 of your Benched Grass Pokemon. Then, shuffle your deck."},
            {"name_en": "Leaf Step"},
        ],
    },
    "004": {  # Snivy
        "attacks": [{"name_en": "Reckless Charge", "effect": "This Pokemon does 10 damage to itself."}],
    },
    "005": {  # Servine
        "attacks": [{"name_en": "Solar Cutter"}],
    },
    "006": {  # Serperior
        "attacks": [
            {"name_en": "Royal Command", "effect": "This attack does 20 damage for each Pokemon you have in play."},
            {"name_en": "Solar Winder", "effect": "If you have Rosa's Encouragement in your discard pile, this attack does 150 more damage."},
        ],
    },
    "007": {  # Scatterbug
        "attacks": [{"name_en": "Gnaw"}],
    },
    "008": {  # Spewpa
        "attacks": [{"name_en": "Hide", "effect": "Flip a coin. If heads, during your opponent's next turn, prevent all damage and effects from attacks done to this Pokemon."}],
    },
    "009": {  # Vivillon
        "abilities": [{"name": "Big Wings", "effect": "Once during your turn, you may have your opponent shuffle their hand and put all of those cards on the bottom of their deck. Then, your opponent draws 4 cards."}],
        "attacks": [{"name_en": "Blow Through", "effect": "If there is a Stadium in play, this attack does 60 more damage."}],
    },
    "010": {  # Rowlet
        "attacks": [
            {"name_en": "Find a Friend", "effect": "Search your deck for a Pokemon, reveal it, and put it into your hand. Then, shuffle your deck."},
            {"name_en": "Tackle"},
        ],
    },
    "011": {  # Dartrix
        "attacks": [
            {"name_en": "Leafage"},
            {"name_en": "Phaser Shot", "effect": "Discard all Energy attached to this Pokemon. Choose 1 of your opponent's Pokemon. This attack does 90 damage to that Pokemon. (Don't apply Weakness and Resistance for Benched Pokemon.)"},
        ],
    },
    "012": {  # Decidueye ex
        "abilities": [{"name": "Sniper Eye", "effect": "If your opponent has exactly 4 cards in their hand, ignore all Colorless in this Pokemon's attack costs."}],
        "attacks": [{"name_en": "Crush Arrow", "effect": "Discard an Energy from your opponent's Active Pokemon."}],
    },
    # --- Fire ---
    "013": {  # Fletchinder
        "attacks": [{"name_en": "Flare"}],
    },
    "014": {  # Talonflame
        "abilities": [{"name": "Sky Hunt", "effect": "Once during your turn, you may flip a coin. If heads, your opponent discards a random card from their hand."}],
        "attacks": [{"name_en": "Fire Wing"}],
    },
    "015": {  # Salandit
        "attacks": [{"name_en": "Fire Claws"}],
    },
    "016": {  # Salazzle ex
        "attacks": [
            {"name_en": "Nasty Plot", "effect": "Search your deck for up to 2 cards and put them into your hand. Then, shuffle your deck."},
            {"name_en": "Fatal Nail", "effect": "Your opponent's Active Pokemon is now Poisoned and Burned. Switch this Pokemon with 1 of your Benched Pokemon."},
        ],
    },
    "017": {  # Turtonator
        "abilities": [{"name": "Thorny Shell", "effect": "When this Pokemon takes damage from an attack from your opponent's Pokemon while it is in the Active Spot, discard an Energy from the attacking Pokemon."}],
        "attacks": [{"name_en": "Heat Breath", "effect": "Flip a coin. If heads, this attack does 80 more damage."}],
    },
    # --- Water ---
    "018": {  # Seel
        "attacks": [{"name_en": "Rain Splash"}, {"name_en": "Wave Splash"}],
    },
    "019": {  # Dewgong
        "abilities": [{"name": "Wash Out", "effect": "As often as you like during your turn, you may move a Water Energy from your Benched Pokemon to your Active Pokemon."}],
        "attacks": [{"name_en": "Wave Splash"}],
    },
    "020": {  # Staryu
        "attacks": [{"name_en": "Water Gun"}],
    },
    "021": {  # Mega Starmie ex
        "attacks": [
            {"name_en": "Jet Blow", "effect": "This attack also does 50 damage to 1 of your opponent's Benched Pokemon. (Don't apply Weakness and Resistance for Benched Pokemon.)"},
            {"name_en": "Nebula Beam", "effect": "This attack's damage isn't affected by Weakness, Resistance, or any effects on your opponent's Active Pokemon."},
        ],
    },
    "022": {  # Lapras ex (ME3 only — not in M3 main 80)
        "attacks": [
            {"name_en": "Hydro Turn", "effect": "Attach up to 2 Basic Water Energy from your discard pile to 1 of your Benched Pokemon."},
            {"name_en": "Surf"},
        ],
    },
    "023": {  # Amaura
        "attacks": [{"name_en": "Icy Wind", "effect": "Your opponent's Active Pokemon is now Asleep."}],
    },
    "024": {  # Aurorus
        "abilities": [{"name": "Tundra Wall", "effect": "While this Pokemon is in play, all of your Pokemon that have a Water Energy attached take 50 less damage from attacks from your opponent's Pokemon. This Ability does not stack."}],
        "attacks": [{"name_en": "Freezing Chill", "effect": "During your opponent's next turn, the Defending Pokemon can't attack."}],
    },
    "025": {  # Volcanion
        "attacks": [
            {"name_en": "Volcanic Strength"},
            {"name_en": "Powerful Steam", "effect": "Flip a coin for each Water Energy attached to this Pokemon. This attack does 90 damage for each heads."},
        ],
    },
    # --- Lightning ---
    "026": {  # Shinx
        "attacks": [{"name_en": "Double Scratch", "effect": "Flip 2 coins. This attack does 10 damage for each heads."}],
    },
    "027": {  # Luxio
        "abilities": [{"name": "Roar of the Tiger", "effect": "If your opponent's Active Pokemon is a Pokemon ex, you can evolve this Pokemon on your first turn, or on the first turn this Pokemon is put into play."}],
        "attacks": [{"name_en": "Zzzap"}],
    },
    "028": {  # Luxray
        "attacks": [
            {"name_en": "Pressure", "effect": "This attack does 70 damage for each Prize card you have taken."},
            {"name_en": "Strong Bolt", "effect": "Discard 2 Energy from this Pokemon."},
        ],
    },
    "029": {  # Dedenne
        "attacks": [
            {"name_en": "Tail Generation", "effect": "For each Energy attached to all of your opponent's Pokemon, you may attach a Basic Lightning Energy from your discard pile to your Lightning Pokemon in any way you like."},
            {"name_en": "Thunder Shock", "effect": "Flip a coin. If heads, your opponent's Active Pokemon is now Paralyzed."},
        ],
    },
    # --- Psychic ---
    "030": {  # Clefairy
        "attacks": [
            {"name_en": "Follow Me", "effect": "Switch 1 of your opponent's Benched Pokemon with their Active Pokemon."},
            {"name_en": "Flop"},
        ],
    },
    "031": {  # Mega Clefable ex
        "abilities": [{"name": "Wings of Light", "effect": "Prevent all effects of your opponent's Abilities done to this Pokemon."}],
        "attacks": [{"name_en": "Shooting Moon", "effect": "You may discard up to 4 Energy cards from your hand. If you do, this attack does 40 more damage for each card discarded in this way."}],
    },
    "032": {  # Mawile
        "attacks": [{"name_en": "Double Eater", "effect": "Discard up to 2 Energy cards from your hand. This attack does 60 damage for each card discarded in this way."}],
    },
    "033": {  # Espurr
        "attacks": [
            {"name_en": "Nap", "effect": "Heal 20 damage from this Pokemon."},
            {"name_en": "Stampede"},
        ],
    },
    "034": {  # Meowstic
        "attacks": [
            {"name_en": "Perplex", "effect": "Your opponent's Active Pokemon is now Confused."},
            {"name_en": "Psychic", "effect": "This attack does 30 more damage for each Energy attached to your opponent's Active Pokemon."},
        ],
    },
    "035": {  # Spritzee
        "attacks": [
            {"name_en": "Sweet Scent", "effect": "Heal 30 damage from 1 of your Pokemon."},
            {"name_en": "Ram"},
        ],
    },
    "036": {  # Aromatisse
        "abilities": [{"name": "Fragrance Collection", "effect": "Once during your turn, you may search your deck for up to 2 Basic Psychic Energy, reveal them, and put them into your hand. Then, shuffle your deck."}],
        "attacks": [{"name_en": "Drain Kiss", "effect": "Heal 30 damage from this Pokemon."}],
    },
    # --- Fighting ---
    "037": {  # Nosepass
        "attacks": [{"name_en": "Avalanche"}],
    },
    "038": {  # Probopass
        "attacks": [
            {"name_en": "Avalanche"},
            {"name_en": "Nose Bumper", "effect": "Discard 3 Energy from this Pokemon."},
        ],
    },
    "039": {  # Hippopotas
        "attacks": [
            {"name_en": "Sand Attack", "effect": "During your opponent's next turn, if the Defending Pokemon tries to use an attack, your opponent flips a coin. If tails, that attack doesn't happen."},
            {"name_en": "Bite"},
        ],
    },
    "040": {  # Hippowdon
        "attacks": [
            {"name_en": "Tornado Drill", "effect": "If you played Tarragon from your hand during this turn, discard the top 3 cards from your opponent's deck."},
            {"name_en": "Heavy Impact"},
        ],
    },
    "041": {  # Landorus
        "attacks": [
            {"name_en": "Rock Tumble", "effect": "This attack's damage isn't affected by Resistance."},
            {"name_en": "Screw Knuckle", "effect": "Return an Energy card attached to this Pokemon to your hand."},
        ],
    },
    "042": {  # Binacle
        "attacks": [
            {"name_en": "Double Draw", "effect": "Draw 2 cards."},
            {"name_en": "Scratch"},
        ],
    },
    "043": {  # Barbaracle
        "abilities": [{"name": "Stone Arms", "effect": "Once during your turn, you may attach a Basic Fighting Energy from your hand to 1 of your Fighting Pokemon."}],
        "attacks": [{"name_en": "Hammer In"}],
    },
    "044": {  # Tyrunt
        "attacks": [{"name_en": "Get Angry", "effect": "This attack does 20 damage times the number of damage counters on this Pokemon."}],
    },
    "045": {  # Tyrantrum
        "abilities": [{"name": "Tyrannoguts", "effect": "If this Pokemon has any Special Energy attached, it gets +150 HP."}],
        "attacks": [{"name_en": "Wreak Havoc", "effect": "Flip a coin until you get tails. For each heads, discard the top card of your opponent's deck."}],
    },
    "046": {  # Hawlucha
        "attacks": [{"name_en": "Revenge Kick", "effect": "If your Benched Pokemon have any damage counters on them, this attack does 60 more damage."}],
    },
    "047": {  # Mega Zygarde ex
        "attacks": [
            {"name_en": "Gaia Wave", "effect": "During your opponent's next turn, this Pokemon takes 30 less damage from attacks (after applying Weakness and Resistance)."},
            {"name_en": "Nullifying Zero", "effect": "For each of your opponent's Pokemon, flip a coin. If heads, this attack does 150 damage to that Pokemon. (Don't apply Weakness and Resistance for Benched Pokemon.)"},
        ],
    },
    # --- Darkness ---
    "048": {  # Gastly
        "attacks": [{"name_en": "Surprise Attack", "effect": "Flip a coin. If tails, this attack does nothing."}],
    },
    "049": {  # Haunter
        "attacks": [{"name_en": "Haunt", "effect": "Put 3 damage counters on your opponent's Active Pokemon."}],
    },
    "050": {  # Gengar
        "abilities": [{"name": "Infinite Shadow", "effect": "If this Pokemon would be Knocked Out by damage from an opponent's Pokemon's attack, instead of discarding it, return it to your hand. (Discard all other cards attached to this Pokemon that are not Pokemon.)"}],
        "attacks": [{"name_en": "Mind Jack", "effect": "This attack does 30 more damage for each of your opponent's Benched Pokemon."}],
    },
    "051": {  # Skorupi
        "attacks": [{"name_en": "Poison Jab", "effect": "Your opponent's Active Pokemon is now Poisoned."}],
    },
    "052": {  # Drapion
        "attacks": [
            {"name_en": "Wrack Down"},
            {"name_en": "Hazard Tail", "effect": "This Pokemon does 70 damage to itself. Your opponent's Active Pokemon is now Poisoned and Paralyzed."},
        ],
    },
    "053": {  # Yveltal ex
        "attacks": [
            {"name_en": "Death Soul", "effect": "Knock Out each of your opponent's Pokemon that has 50 HP or less remaining."},
            {"name_en": "Dark Strike", "effect": "During your next turn, this Pokemon can't use Dark Strike."},
        ],
    },
    "054": {  # Chien-Pao
        "attacks": [
            {"name_en": "Strafe", "effect": "You may switch this Pokemon with 1 of your Benched Pokemon."},
            {"name_en": "Rising Blade", "effect": "If your opponent's Active Pokemon is a Pokemon ex, this attack does 80 more damage."},
        ],
    },
    # --- Metal ---
    "055": {  # Mega Skarmory ex
        "attacks": [{"name_en": "Sonic Ripper", "effect": "Shuffle all Energy from this Pokemon into your deck. This attack does 220 damage to 1 of your opponent's Pokemon. (Don't apply Weakness and Resistance for Benched Pokemon.)"}],
    },
    "056": {  # Honedge
        "attacks": [{"name_en": "Cut"}],
    },
    "057": {  # Doublade
        "attacks": [{"name_en": "Sword Stash", "effect": "You may reveal any number of Honedge, Doublade, and Aegislash from your hand. This attack does 60 damage for each card you revealed."}],
    },
    "058": {  # Aegislash
        "attacks": [
            {"name_en": "Slash"},
            {"name_en": "Metal Slash", "effect": "This Pokemon can't attack during your next turn."},
        ],
    },
    "059": {  # Klefki
        "attacks": [{"name_en": "Memory Lock", "effect": "Choose an attack on your opponent's Active Pokemon. During your opponent's next turn, the Defending Pokemon can't use that attack."}],
    },
    # --- Colorless ---
    "060": {  # Rattata
        "attacks": [{"name_en": "Take Down", "effect": "This Pokemon does 10 damage to itself."}],
    },
    "061": {  # Raticate
        "attacks": [
            {"name_en": "Scrape Off", "effect": "Before doing damage, you may discard a Pokemon Tool attached to your opponent's Active Pokemon."},
            {"name_en": "Countering Incisors", "effect": "This attack does 40 damage for each damage counter on all of your Benched Rattata."},
        ],
    },
    "062": {  # Meowth ex
        "abilities": [{"name": "Last-Ditch Catch", "effect": "Once during your turn, when you play this Pokemon from your hand onto your Bench, you may use this Ability. Search your deck for a Supporter card, reveal it, and put it into your hand. Then, shuffle your deck."}],
        "attacks": [{"name_en": "Tuck Tail", "effect": "Put this Pokemon and all attached cards into your hand."}],
    },
    "063": {  # Snorlax
        "attacks": [
            {"name_en": "Big Eater", "effect": "Flip a coin until you get tails. For each heads, you may search your deck for a Basic Energy and attach it to this Pokemon. Then, shuffle your deck."},
            {"name_en": "Collapse", "effect": "This Pokemon is now Asleep."},
        ],
    },
    "064": {  # Bunnelby
        "attacks": [{"name_en": "Smash Kick"}],
    },
    "065": {  # Diggersby
        "attacks": [
            {"name_en": "Earthquake", "effect": "This attack does 30 damage to each of your Benched Pokemon. (Don't apply Weakness and Resistance for Benched Pokemon.)"},
            {"name_en": "Whap Down"},
        ],
    },
    "066": {  # Fletchling
        "attacks": [
            {"name_en": "Chirp", "effect": "Search your deck for up to 2 Pokemon with Fighting Resistances, reveal them, and put them into your hand. Then, shuffle your deck."},
            {"name_en": "Peck"},
        ],
    },
    "067": {  # Furfrou
        "attacks": [
            {"name_en": "Hand Cut", "effect": "Discard random cards from your opponent's hand until they have 5 cards in their hand."},
            {"name_en": "Headbutt"},
        ],
    },
}

# Trainer enrichments (card numbers 068-088 in ME3)
TRAINER_ENRICHMENTS = {
    "068": {"effect": "You may play this card as a 60 HP Basic Colorless Pokemon. This Pokemon can't be affected by Special Conditions and can't retreat. At any time during your turn, you may discard this card from play. Ability: Imitating Jaw - If this Pokemon is your Active Pokemon, attacks from your opponent's Active Pokemon do 30 less damage.", "subcategory": "Item"},
    "069": {"effect": "You may play this card as a 60 HP Basic Colorless Pokemon. This Pokemon can't be affected by Special Conditions and can't retreat. At any time during your turn, you may discard this card from play. Ability: Protective Sail - This Pokemon can't be affected by the effects of Supporter cards played from your opponent's hand.", "subcategory": "Item"},
    "070": {"effect": "The Mega Zygarde ex this card is attached to can use the attacks on this card. [F][F][F][F] Geobuster: 350 damage. Discard all Energy from this Pokemon.", "subcategory": "Pokemon Tool"},
    "071": {"effect": "Flip a coin. If heads, discard an Energy attached to your opponent's Active Pokemon.", "subcategory": "Item"},
    "072": {"effect": "Search your deck for a Basic Energy card, reveal it, and put it into your hand. Then, shuffle your deck.", "subcategory": "Item"},
    "073": {"effect": "Your opponent reveals their hand. Choose an Energy card you find there and put it on the bottom of your opponent's deck.", "subcategory": "Item"},
    "074": {"effect": "Look at the top card of your opponent's deck. You may discard that card.", "subcategory": "Item"},
    "075": {"effect": "Heal 150 damage from 1 of your Psychic Pokemon.", "subcategory": "Supporter"},
    "076": {"effect": "Each player shuffles their hand into their deck and draws 4 cards.", "subcategory": "Supporter"},
    "077": {"effect": "Once during each player's turn, that player may search their deck for a Basic Pokemon and put it onto their Bench. Then, that player shuffles their deck. If a player uses this effect, their turn ends.", "subcategory": "Stadium"},
    "078": {"effect": "Heal 20 damage and 1 Special Condition from your Active Pokemon.", "subcategory": "Item"},
    "079": {"effect": "Discard any number of cards from your hand. Then, draw cards until you have 5 cards in your hand.", "subcategory": "Supporter"},
    "080": {"effect": "Flip a coin. If heads, search your deck for a Pokemon, reveal it, and put it into your hand. Then, shuffle your deck.", "subcategory": "Item"},
    "081": {"effect": "Search your deck for a Pokemon that doesn't have a Rule Box, reveal it, and put it into your hand. Then, shuffle your deck.", "subcategory": "Item"},
    "082": {"effect": "Switch 1 of your opponent's Benched Pokemon with their Active Pokemon.", "subcategory": "Item"},
    "083": {"effect": "Heal 30 damage from 1 of your Pokemon.", "subcategory": "Item"},
    "084": {"effect": "You can only use this card if you have more Prize cards remaining than your opponent. Attach up to 2 Basic Energy cards from your discard pile to 1 of your Stage 2 Pokemon.", "subcategory": "Supporter"},
    "085": {"effect": "Put up to 4 in any combination of Fighting Pokemon and Basic Fighting Energy from your discard pile into your hand.", "subcategory": "Supporter"},
}

ENERGY_ENRICHMENTS = {
    "086": {"effect": "This card provides Grass Energy while attached to a Pokemon. The Grass Pokemon this card is attached to gets +20 HP."},
    "087": {"effect": "This card provides Fighting Energy while attached to a Pokemon. Prevent all effects of attacks used by your opponent's Pokemon done to the Fighting Pokemon this card is attached to. (Existing effects are not removed. Damage is not an effect.)"},
    "088": {"effect": "This card provides Psychic Energy while attached to a Pokemon. When you attach this card from your hand to 1 of your Psychic Pokemon, you may search your deck for 2 Basic Psychic Pokemon and put them onto your Bench. Then, shuffle your deck."},
}


def enrich_card(card, enrichment):
    """Apply enrichment data to a card dict."""
    card = copy.deepcopy(card)
    if "abilities" in enrichment:
        card["abilities"] = enrichment["abilities"]
    if "attacks" in enrichment and "attacks" in card:
        for i, atk_enrich in enumerate(enrichment["attacks"]):
            if i < len(card["attacks"]):
                if "effect" in atk_enrich:
                    card["attacks"][i]["effect"] = atk_enrich["effect"]
    if "effect" in enrichment:
        card["effect"] = enrichment["effect"]
    if "subcategory" in enrichment:
        card["subcategory"] = enrichment["subcategory"]
    return card


def main():
    m3 = json.loads(M3_PATH.read_text())
    me3 = json.loads(ME3_PATH.read_text())

    # Enrich M3 (JP) — add abilities and attack effects (in English, since JP text isn't available)
    m3_enriched = 0
    for num, enrichment in ENRICHMENTS.items():
        if num in m3["cards"]:
            m3["cards"][num] = enrich_card(m3["cards"][num], enrichment)
            m3_enriched += 1

    # Enrich ME3 (EN) — add abilities, attack effects, trainer effects
    me3_enriched = 0
    for num, enrichment in ENRICHMENTS.items():
        if num in me3["cards"]:
            me3["cards"][num] = enrich_card(me3["cards"][num], enrichment)
            me3_enriched += 1

    # Trainer enrichments (ME3 has these, M3 may have some too)
    for num, enrichment in {**TRAINER_ENRICHMENTS, **ENERGY_ENRICHMENTS}.items():
        if num in me3["cards"]:
            me3["cards"][num] = enrich_card(me3["cards"][num], enrichment)
            me3_enriched += 1
        if num in m3["cards"]:
            m3["cards"][num] = enrich_card(m3["cards"][num], enrichment)
            m3_enriched += 1

    # For secret rares (089+) in ME3 that share the same base card,
    # copy abilities from the main set version
    for num, card in me3["cards"].items():
        if int(num) > 88 and card.get("category") == "Pokemon":
            # Find matching main set card by name
            for main_num, main_card in me3["cards"].items():
                if int(main_num) <= 88 and main_card.get("name") == card.get("name"):
                    if "abilities" in main_card and "abilities" not in card:
                        card["abilities"] = copy.deepcopy(main_card["abilities"])
                    # Copy attack effects too
                    if "attacks" in main_card and "attacks" in card:
                        for i, atk in enumerate(card["attacks"]):
                            if i < len(main_card["attacks"]) and "effect" in main_card["attacks"][i] and "effect" not in atk:
                                atk["effect"] = main_card["attacks"][i]["effect"]
                    break

    # Add jpSetId to ME3 for the translation mapping
    if "jpSetId" not in me3:
        me3["jpSetId"] = "M3"

    M3_PATH.write_text(json.dumps(m3, indent=2, ensure_ascii=False))
    ME3_PATH.write_text(json.dumps(me3, indent=2, ensure_ascii=False))
    print(f"Enriched M3: {m3_enriched} cards patched -> {M3_PATH}")
    print(f"Enriched ME3: {me3_enriched} cards patched -> {ME3_PATH}")


if __name__ == "__main__":
    main()
