#!/usr/bin/env python3
"""
Scrape card data from Serebii to enrich sideload files.

Fetches: weakness, resistance, abilities, attack costs/effects, trainer effects,
subcategory, and fills empty attacks (M1L).

Serebii URL pattern: https://www.serebii.net/card/{setslug}/{num:03d}.shtml
"""
import json, pathlib, re, time, sys, html as html_mod
from urllib.request import urlopen, Request

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"

SET_SLUGS = {
    "M1S":  "megasymphonia",
    "M1L":  "megabrave",
    "M2":   "infernox",
    "M3":   "nihilzero",
    "M4":   "ninjaspinner",
    "ME3":  "perfectorder",
    "ME4":  "ninjaspinner",
    "SV6a": "nightwanderer",
}

ENERGY_TYPES = ["Grass", "Fire", "Water", "Lightning", "Psychic",
                "Fighting", "Darkness", "Metal", "Dragon", "Colorless", "Fairy"]


def fetch_page(url):
    for attempt in range(3):
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0 (Pokemon TCG data enrichment)"})
            with urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception:
            if attempt < 2:
                time.sleep(2)
            else:
                return None


def extract_energy_images(html_fragment):
    """Extract energy types from <img src="/card/image/{type}.png"> tags."""
    types = []
    for m in re.finditer(r'/card/image/(\w+)\.png', html_fragment):
        t = m.group(1).capitalize()
        if t in ENERGY_TYPES:
            types.append(t)
    return types


def clean_text(s):
    """Strip HTML tags and clean text."""
    s = re.sub(r'<br\s*/?>', ' ', s)
    s = re.sub(r'<[^>]+>', '', s)
    s = html_mod.unescape(s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def parse_serebii_card(raw_html):
    """Extract card data from a Serebii card page."""
    result = {}

    # === WEAKNESS ===
    # Pattern: <b>Weakness</b></td> ... <img src="/card/image/{type}.png">x2
    wm = re.search(
        r'<b>Weakness</b>.*?/card/image/(\w+)\.png.*?x2',
        raw_html, re.DOTALL | re.IGNORECASE
    )
    if wm:
        wtype = wm.group(1).capitalize()
        if wtype in ENERGY_TYPES:
            result["weakness"] = {"type": wtype, "value": "x2"}

    # === RESISTANCE ===
    # Must be within same table row as Weakness (close proximity)
    res_section = re.search(
        r'<b>Resistance</b></td>\s*<td[^>]*>(.*?)</td>',
        raw_html, re.DOTALL | re.IGNORECASE
    )
    if res_section:
        res_content = res_section.group(1)
        rm = re.search(r'/card/image/(\w+)\.png', res_content)
        rv = re.search(r'[-−](\d{2})\b', res_content)
        if rm and rv:
            rtype = rm.group(1).capitalize()
            if rtype in ENERGY_TYPES:
                result["resistance"] = {"type": rtype, "value": f"-{rv.group(1)}"}

    # === RETREAT COST ===
    ret_section = re.search(
        r'<b>Retreat Cost</b></td>\s*<td[^>]*>(.*?)</td>',
        raw_html, re.DOTALL | re.IGNORECASE
    )
    if ret_section:
        retreat_imgs = re.findall(r'/card/image/colorless\.png', ret_section.group(1))
        if retreat_imgs:
            result["retreat"] = len(retreat_imgs)

    # === TRAINER SUBCATEGORY ===
    # Try "Trainer - Item" format first
    subcat_m = re.search(
        r'Trainer\s*[-\u2013]\s*(Item|Supporter|Stadium|Pok[eé]mon Tool)',
        raw_html, re.IGNORECASE
    )
    if subcat_m:
        result["subcategory"] = subcat_m.group(1).replace("Pokémon", "Pokemon").replace("Pok\u00e9mon", "Pokemon")

    # === TRAINER/ENERGY EFFECT ===
    # Serebii uses <i>Trainer</i>, <i>Supporter</i>, <i>Stadium</i>, <i>Item</i>, or <i>Special Energy</i>
    for card_type_label in ['Trainer', 'Supporter', 'Stadium', 'Item', 'Pok[eé]mon Tool', 'Special Energy', 'Energy']:
        effect_section = re.search(
            r'<i>' + card_type_label + r'</i>.*?<td[^>]*colspan="3"[^>]*>.*?<p>\s*(.*?)\s*</p>',
            raw_html, re.DOTALL | re.IGNORECASE
        )
        if effect_section:
            effect_text = clean_text(effect_section.group(1))
            # Remove the "You may play only 1 Supporter..." flavor text
            effect_text = re.sub(r'\s*You may play only \d+ Supporter.*$', '', effect_text)
            effect_text = re.sub(r'\s*You may play only \d+ Stadium.*$', '', effect_text)
            if effect_text and len(effect_text) > 5:
                result["trainer_effect"] = effect_text
                # Also set subcategory from the label if not already found
                if "subcategory" not in result:
                    label = card_type_label.replace('Pok[eé]mon', 'Pokemon')
                    if label in ('Supporter', 'Stadium', 'Item'):
                        result["subcategory"] = label
                    elif label == 'Pok[eé]mon Tool':
                        result["subcategory"] = 'Pokemon Tool'
                    elif label == 'Trainer':
                        result["subcategory"] = 'Item'  # Generic "Trainer" = Item
            break

    # === ATTACKS ===
    # Attack rows: <td> with energy images </td> <td> attack name + effect </td> <td> damage </td>
    # Pattern: energy cost td, then attack name in <b>, effect text, then damage td
    attacks = []
    # Find attack rows: look for td cells with energy images followed by attack name cells
    attack_pattern = re.compile(
        r'<td[^>]*class="medium"[^>]*align="center"[^>]*>\s*'
        r'((?:<img[^>]*/card/image/\w+\.png[^>]*>\s*)+)'  # energy cost images
        r'</td>\s*'
        r'<td[^>]*class="medium"[^>]*>'                    # attack name cell
        r'(.*?)</td>\s*'                                     # attack content
        r'<td[^>]*class="main"[^>]*><b>(.*?)</b></td>',     # damage cell
        re.DOTALL
    )

    # Also try alternate layout where cost is in first column
    attack_pattern2 = re.compile(
        r'<td[^>]*class="medium"[^>]*>\s*\n?\s*'
        r'((?:<img[^>]*/card/image/\w+\.png[^>]*>[\s\n]*)+)'  # energy cost
        r'</td>\s*'
        r'<td[^>]*class="medium"[^>]*>'                         # name/effect cell
        r'\s*<span[^>]*><[^>]*><b>(.*?)</b></[^>]*></span>'     # attack name in <b>
        r'(.*?)</td>\s*'                                          # effect text
        r'<td[^>]*[^>]*><b>(.*?)</b></td>',                      # damage
        re.DOTALL
    )

    # Try the more specific pattern first; fall back only if it finds nothing
    for pattern in [attack_pattern2, attack_pattern]:
        for m in pattern.finditer(raw_html):
            cost_html = m.group(1)
            cost = extract_energy_images(cost_html)

            if pattern == attack_pattern2:
                name = clean_text(m.group(2))
                effect_raw = clean_text(m.group(3))
                damage_raw = clean_text(m.group(4))
            else:
                name_and_effect = clean_text(m.group(2))
                name_m = re.match(r'^(.+?)(?:\s+(.+))?$', name_and_effect)
                name = name_m.group(1) if name_m else name_and_effect
                effect_raw = name_m.group(2) if name_m and name_m.group(2) else ""
                damage_raw = clean_text(m.group(3))

            atk = {"name": name}
            if cost:
                atk["cost"] = cost
            if damage_raw:
                try:
                    atk["damage"] = int(damage_raw)
                except ValueError:
                    atk["damage"] = damage_raw
            if effect_raw:
                atk["effect"] = effect_raw

            attacks.append(atk)
        if attacks:
            break  # Don't try fallback pattern if primary found results

    # Deduplicate attacks by name (multiple regex patterns may match same attack)
    if attacks:
        seen = set()
        deduped = []
        for a in attacks:
            if a["name"] not in seen:
                seen.add(a["name"])
                deduped.append(a)
        result["attacks"] = deduped

    # === ABILITIES ===
    # Serebii shows abilities differently — sometimes inline before attacks
    # Look for text between HP line and first attack that contains ability keywords
    # Pattern on card 005: "Wild Growth Each Basic Energy..."
    # The ability section is between the HR after HP and the first attack row

    # Strategy: get the stripped text between "HP" and "Weakness", then look for
    # ability-like text that isn't an attack
    hp_to_weak = re.search(
        r'HP\s*(?:&nbsp;)?\s*</b></font></td>.*?<b>Weakness</b>',
        raw_html, re.DOTALL
    )
    if hp_to_weak:
        section = hp_to_weak.group(0)
        section_text = clean_text(section)

        # Look for ability: text before attack patterns that sounds like an ability
        # Abilities often start with a name, then describe a once-per-turn effect
        # Look for text that's NOT an attack (no energy cost, no damage)
        # In Serebii, abilities may be rendered as plain text before attacks

        # Check for explicit "Ability" label
        abil_m = re.search(r'Ability\s*[:\s]+\s*(.+?)(?=\s*(?:Weakness|$))', section_text)
        if not abil_m:
            # Try finding ability-like text: a capitalized phrase followed by effect text
            # between card info and attacks. This is in the text stripped area.
            # Split by attack names we found
            atk_names = [a["name"] for a in attacks]
            remaining_text = section_text
            # Remove known parts
            for part in ["HP", "Weakness"]:
                remaining_text = remaining_text.replace(part, "")
            # Remove attack-related text
            for a in attacks:
                if a["name"] in remaining_text:
                    idx = remaining_text.find(a["name"])
                    remaining_text = remaining_text[:idx]
                    break

            remaining_text = remaining_text.strip()
            if remaining_text and len(remaining_text) > 20:
                # Try to split into ability name and effect
                # Pattern: "Ability Name" followed by effect sentence
                parts = re.match(
                    r'^(.+?)\s+(Once during|When|If|As often|At any|This Pok|Prevent|During|After|'
                    r'You may|Each|Your|The|Whenever|Put|Search|Look|Discard|Draw|Choose|Flip|'
                    r'Move|Attach|Switch|Heal|Remove|Place|Return|Shuffle|Before|Any|All|Ignore|'
                    r'While|Pok[eé]mon|Basic|Damage|At the|Cards|Energy|Attacks|While this)(.+)',
                    remaining_text
                )
                if parts:
                    abil_name = parts.group(1).strip()
                    abil_effect = (parts.group(2) + parts.group(3)).strip()
                    # Validate: ability name should be short (1-5 words)
                    if 1 <= len(abil_name.split()) <= 6 and len(abil_effect) > 10:
                        result["abilities"] = [{"name": abil_name, "effect": abil_effect}]

    return result


def enrich_set(set_id):
    """Enrich a sideload set with Serebii data."""
    slug = SET_SLUGS.get(set_id)
    if not slug:
        print(f"  No Serebii slug for {set_id}")
        return

    path = DATA / f"{set_id}.json"
    data = json.loads(path.read_text())
    cards = data["cards"]

    stats = {"weakness": 0, "resistance": 0, "abilities": 0, "attacks": 0,
             "subcategory": 0, "trainer_effect": 0, "total_fetched": 0}

    for num in sorted(cards.keys()):
        card = cards[num]
        cat = card.get("category", "")

        url = f"https://www.serebii.net/card/{slug}/{num}.shtml"
        html = fetch_page(url)
        if not html:
            print(f"    Failed to fetch {set_id}-{num}")
            time.sleep(1)
            continue

        stats["total_fetched"] += 1
        parsed = parse_serebii_card(html)

        if cat == "Pokemon":
            if "weakness" not in card and "weakness" in parsed:
                card["weakness"] = parsed["weakness"]
                stats["weakness"] += 1
            if "resistance" not in card and "resistance" in parsed:
                card["resistance"] = parsed["resistance"]
                stats["resistance"] += 1
            if "abilities" not in card and "abilities" in parsed:
                card["abilities"] = parsed["abilities"]
                stats["abilities"] += 1
            # Fill empty attacks from scrape
            if (not card.get("attacks") or len(card.get("attacks", [])) == 0) and "attacks" in parsed:
                card["attacks"] = parsed["attacks"]
                stats["attacks"] += 1
            # Add missing cost/effect to existing attacks
            elif card.get("attacks") and "attacks" in parsed:
                for i, (ja, en) in enumerate(zip(card["attacks"], parsed["attacks"])):
                    if "cost" not in ja and "cost" in en:
                        ja["cost"] = en["cost"]
                    if "effect" not in ja and "effect" in en:
                        ja["effect"] = en["effect"]

        elif cat == "Trainer":
            if "subcategory" not in card and "subcategory" in parsed:
                card["subcategory"] = parsed["subcategory"]
                stats["subcategory"] += 1
            if "effect" not in card and "trainer_effect" in parsed:
                card["effect"] = parsed["trainer_effect"]
                stats["trainer_effect"] += 1

        elif cat == "Energy":
            if "effect" not in card and "trainer_effect" in parsed:
                card["effect"] = parsed["trainer_effect"]
                stats["trainer_effect"] += 1

        # Be polite to Serebii
        time.sleep(0.3)

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"  {set_id}: fetched {stats['total_fetched']} pages")
    print(f"    weakness:{stats['weakness']} res:{stats['resistance']} abil:{stats['abilities']}")
    print(f"    attacks:{stats['attacks']} subcat:{stats['subcategory']} trainer_eff:{stats['trainer_effect']}")
    return stats


if __name__ == "__main__":
    sets_to_enrich = sys.argv[1:] if len(sys.argv) > 1 else ["M1S", "M1L", "M2"]
    for sid in sets_to_enrich:
        print(f"Enriching {sid}...")
        enrich_set(sid)
        print()
