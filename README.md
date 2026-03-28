# JP → EN Pokemon TCG Card Matcher

A client-side tool to find the English equivalent of a Japanese Pokemon TCG card. Works offline as a PWA.

**Live:** [dgallitelli.github.io/pokemon-tcg-jp-en-matcher](https://dgallitelli.github.io/pokemon-tcg-jp-en-matcher/)

## How It Works

1. Enter a Japanese set ID (e.g. `SV5a`, `M3`) and card number
2. The tool fetches the Japanese card from the [TCGdex API](https://tcgdex.dev/) or local sideload data
3. Finds the English equivalent using multiple matching strategies (see below)
4. Displays both cards side by side with a confidence score

## Matching Strategies

### Pokemon Cards
Uses the Pokedex ID to find the English Pokemon name, then searches TCGdex for English cards matching name + HP. Candidates are scored by comparing:

| Signal | Weight | Why |
|--------|--------|-----|
| Illustrator | 25 | Same artist = same print |
| HP | 15 | Narrows to the right variant |
| Attack count & damage | 22 | Structural match |
| Attack costs | 8 | Additional confirmation |
| Ability count | 7 | Structural match |
| Category | 5 | Pokemon vs Trainer vs Energy |
| Weakness / Resistance | 5 | Confirms type matchup |
| Retreat cost | 3 | Tiebreaker |
| Stage | 3 | Tiebreaker |

### Trainer & Energy Cards
- **Name map lookup** — a built-in JP→EN name dictionary (`TRAINER_NAME_MAP`) covers common trainers, supporters, stadiums, items, and energy cards across all sideloaded sets
- **Sideload translation** — for sets with EN translation sideloads (M3→ME3, M4→ME4), cards are matched directly by dexId, illustrator, energy type, or category-aware card number
- **Serebii fallback** — when no official English print exists, a synthetic translation card is shown using English text scraped from Serebii

### Energy Cards
Matched by energy type keyword (JP type kanji → EN type name: 草→Grass, 炎→Fire, 水→Water, etc.)

## Sideloaded Sets

Sets not yet in TCGdex are sideloaded from local JSON files in `data/`:

| JP Set | EN Translation | Source |
|--------|---------------|--------|
| M1S (Mega Symphonia) | — | Serebii |
| M1L (Mega Brave) | — | Serebii |
| M2 (Inferno X) | — | Serebii |
| M3 (Nihil Zero) | ME3 (Perfect Order) | TCGdex + Serebii |
| M4 (Ninja Spinner) | ME4 (Ninja Spinner) | TCGdex + Serebii |

Card data includes: name, HP, types, stage, attacks (name/cost/damage/effect), abilities, weakness, resistance, retreat cost, illustrator, rarity, trainer effects, and subcategories.

## Features

- **Prev/Next navigation** — step through cards in a set without re-entering numbers
- **Set browser** — visual grid of all cards in a set with category filters (Pokemon/Trainer/Energy)
- **Energy cost rendering** — attack costs shown as colored type badges
- **Deep linking** — shareable URLs like `?set=M3&num=051`
- **PWA / offline support** — service worker caches app shell and sideload data
- **Mobile responsive** — adapts layout for narrow screens

## Data Pipeline

Scripts in `scripts/` maintain the sideload data:

- `scrape_serebii.py` — scrapes Serebii card pages for weakness, resistance, abilities, attacks, trainer effects, subcategories
- `normalize_data.py` — backfills JP sets from EN translations (M4←ME4, M3←ME3) and ensures structural consistency
- `fix_remaining_gaps.py` — manual patches for cards the scraper missed

## Tech

Zero dependencies. Single HTML file. All API calls run in the browser against TCGdex's free public API. No backend, no keys, no build step.

## License

MIT
