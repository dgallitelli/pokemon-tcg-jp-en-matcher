# Limitless TCG Coverage Checker & Scraper — Design Spec

**Date:** 2026-04-18  
**Status:** Approved

## Goal

A single Python script (`scripts/scrape_limitless.py`) that:
1. Checks coverage for all known JP sets — both M* (sideloaded) and SV* (live TCGdex)
2. For M* sets with missing/incomplete EN translations: scrapes the full set from Limitless TCG and writes `data/ME*.json` in the existing format
3. For SV* sets: verifies a random card has an EN match via TCGdex API, reports gaps (no files written)

## Data Sources

- **Limitless TCG** — `https://limitlesstcg.com/cards/jp/{SET}/{NUM}?translate=en` — HTML scrape (BeautifulSoup)
- **TCGdex API** — `https://api.tcgdex.net/v2` — JSON API for SV* set discovery and EN match verification

## M* Sets Configuration

Hardcoded mapping of JP set ID → EN sideload set ID and EN set metadata:

| JP Set | EN Set ID | EN Set Name       | Card Count |
|--------|-----------|-------------------|------------|
| M1S    | ME1       | Mega Symphonia    | 92         |
| M1L    | ME1       | Mega Brave        | 92         |
| M2     | ME2       | Phantasmal Flames | 116        |
| M2a    | ME2a      | MEGA Dream ex     | 193        |
| M3     | ME3       | Perfect Order     | 117        |
| M4     | ME4       | Ninja Spinner     | 120        |

Note: M1S and M1L both map to ME1 (same EN set). M2a gets a new `ME2a` file (currently no EN sideload).

## Coverage Check Logic

### M* sets
Pick card #1 from the existing ME*.json (or the midpoint card). Coverage is **present** if:
- The card exists in the EN sideload
- At least one attack has a non-`—` name **or** the card has a non-null `image` field

Coverage is **missing** if the EN sideload file doesn't exist, is empty, or the sampled card fails the above check.

### SV* sets
1. Fetch all JP sets from `https://api.tcgdex.net/v2/ja/sets` — filter for IDs starting with `SV` (case-insensitive, skip SVLS/SVK/SVLN deck-builder sets)
2. For each SV set: fetch a random card from `https://api.tcgdex.net/v2/ja/sets/{setId}`, then query `https://api.tcgdex.net/v2/en/cards?name={enName}` using the card's dexId for name lookup
3. Report ✅ or ❌ per set — no file writes

## Scraping Logic (M* sets only)

For each card number 1..N in the set:
1. Fetch `https://limitlesstcg.com/cards/jp/{SET}/{NUM}?translate=en`
2. Parse HTML with BeautifulSoup
3. Extract fields (see schema below)
4. Sleep 1 second between requests
5. Write complete `data/ME*.json` when all cards done

### HTML Parsing Strategy

The page is server-rendered. Key elements to extract:

- **Card name**: `<h1>` or title element containing the card name
- **Category/stage**: text like "Pokémon - Basic", "Trainer - Supporter", "Energy - Special Energy"
- **HP**: number adjacent to "HP" label
- **Types**: energy type icons/labels  
- **Attacks**: each attack block has name, cost (energy symbols), damage number, effect text
- **Abilities**: labeled "Ability" with name + effect
- **Weakness/Resistance**: labeled fields
- **Retreat cost**: number of Colorless energy symbols
- **Illustrator**: linked text after "Illus." label
- **Rarity**: text label (Common, Uncommon, Rare, etc.)
- **Image URL**: `<img>` src matching `limitlesstcg.nyc3.cdn.digitaloceanspaces.com`

Energy cost parsing: Limitless uses single-letter abbreviations (G=Grass, R=Fire, W=Water, L=Lightning, P=Psychic, F=Fighting, D=Darkness, M=Metal, C=Colorless, N=Dragon, Y=Fairy). Map these to full type names.

### Output Schema (matches existing ME*.json)

**File structure:**
```json
{
  "id": "ME4",
  "name": "Ninja Spinner",
  "serie": "Mega Evolution",
  "releaseDate": { "en": "2026-05-22" },
  "jpSetId": "M4",
  "cards": {
    "001": { ... },
    "002": { ... }
  }
}
```

**Pokemon card:**
```json
{
  "name": "Weedle",
  "id": "ME4-001",
  "set": { "id": "ME4", "name": "Ninja Spinner" },
  "image": "https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/tpc/M4/M4_1_R_JP_LG.png",
  "category": "Pokemon",
  "hp": 50,
  "types": ["Grass"],
  "stage": "Basic",
  "retreat": 1,
  "dexId": [],
  "rarity": "Common",
  "illustrator": "sowsow",
  "attacks": [
    { "name": "Surprise Attack", "damage": 30, "cost": ["Grass"], "effect": "Flip a coin. If tails, this attack does nothing." }
  ],
  "weakness": { "type": "Fire", "value": "x2" },
  "abilities": []
}
```

**Trainer card:**
```json
{
  "name": "Special Red Card",
  "id": "ME4-072",
  "set": { "id": "ME4", "name": "Ninja Spinner" },
  "image": "https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/tpc/M4/M4_72_R_JP_LG.png",
  "category": "Trainer",
  "subcategory": "Item",
  "rarity": "Uncommon",
  "illustrator": "Shibiru",
  "effect": "You can only play this card if..."
}
```

**Energy card:**
```json
{
  "name": "Nitro Fire Energy",
  "id": "ME4-081",
  "set": { "id": "ME4", "name": "Ninja Spinner" },
  "image": "https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/tpc/M4/M4_81_R_JP_LG.png",
  "category": "Energy",
  "subcategory": "Special Energy",
  "rarity": "Uncommon",
  "illustrator": "Souichirou Gunjima",
  "effect": "As long as this card is attached..."
}
```

`dexId` stays empty `[]` — Limitless doesn't expose Pokédex numbers in the HTML. Existing `dexId` values in current ME*.json files should be preserved where possible (merge, don't overwrite).

## app.js Changes

The EN panel currently shows `null` images for ME1/ME2 sets (Serebii doesn't index them). With Limitless CDN URLs in `image` fields, `renderCard()` will automatically show images — **no app.js changes required** since `renderCard()` already uses `card.image + '/high.webp'` ... wait, Limitless URLs are already full URLs ending in `.png`, not TCGdex-style paths.

**One small change required in `renderCard()`:** The image URL construction is currently `card.image + '/high.webp'`. For Limitless URLs (already full `.png` URLs), this would break. Fix: if `card.image` starts with `http`, use it as-is; otherwise append `/high.webp`.

## Script Output

```
=== M* Coverage Check ===
M1S → ME1: ❌ Missing EN translations — scraping 92 cards...
  [1/92] Tangela... ✓
  [2/92] ...
  Done. Wrote data/ME1.json
M1L → ME1: ✅ Already covered (merged into ME1)
M2  → ME2: ✅ Coverage OK
M3  → ME3: ✅ Coverage OK
M4  → ME4: ❌ Missing images — scraping 120 cards...
  ...
M2a → ME2a: ❌ No EN sideload — scraping 193 cards...

=== SV* Coverage Check ===
SV1S (スカーレットex)     : ✅ EN match found (Scarlet & Violet #5)
SV1V (バイオレットex)      : ✅ EN match found
SV2a (ポケモンカード151)   : ✅ EN match found
...
SV10 (ロケット団の栄光)    : ❌ No EN match found
```

## Out of Scope

- Scraping SV* sets to local files
- Updating `app.js` beyond the `renderCard()` image URL fix
- Updating `SIDELOAD_CONFIG` in `app.js` to add ME2a (separate task)
- Handling sets not on Limitless

## Dependencies

- `requests` (already likely available)
- `beautifulsoup4` — may need `pip install beautifulsoup4`
- `lxml` — optional faster HTML parser
