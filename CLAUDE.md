# Pokémon TCG JP→EN Matcher

## Platform goal

Side-by-side quick reference tool for playing Pokémon TCG with Japanese cards.
The user looks up a JP card mid-game to see its English equivalent instantly.

**Display priority:**
1. If an official English card image is available → show it (the EN card panel is what you show opponents)
2. If no English image is available → show the English text (attacks, abilities, effects)

The layout must always be **side-by-side** (JP left, EN right), adapting panel size to the screen — never stacking vertically.

## Architecture

Single `index.html` — no build step, no dependencies, deploys as a GitHub Pages static site.

**Data sources:**
- `data/M*.json` — JP sideload sets scraped from pokemon-card.com
- `data/ME*.json` — EN translation sideloads built from TCGdex API + Serebii scraping
- TCGdex API (`https://api.tcgdex.net/v2`) — live lookup for standard sets

**JP→EN sideload mapping:**
- M1S / M1L → ME1 (Mega Evolution)
- M2 → ME2 (Phantasmal Flames)
- M3 → ME3 (Perfect Order)
- M4 → ME4 (Ninja Spinner)
- M2a (MEGA Dream ex) — JP only, no EN sideload yet; falls through to TCGdex API matching

## Key invariants

- **Never show a JP card image in the EN panel.** If no EN image exists, show the card placeholder (🃏).
- **Never show JP attack names in the EN panel.** If attack names weren't translated (synthetic EN cards), render them as `—` so only cost + damage + effect are shown.
- EN sideload cards (ME1–ME4) have `image: null` by design — `sideloadImageUrl()` provides Serebii image URLs for ME3/ME4; ME1/ME2 have no Serebii pages and show no image.
- All EN sideloads are pre-fetched at startup (needed for cross-set dexId scanning in step 2b of `doSearch`). JP sideloads are lazy-loaded on first access.

## Data pipeline scripts

Run manually when new sets release:
1. `scrape_m*.py` — scrape JP card data from pokemon-card.com
2. `fetch_tcgdex_en.py` — fetch EN data from TCGdex and backfill JP attack text
3. `scrape_serebii.py` — enrich with weakness/resistance/abilities from Serebii
4. `normalize_data.py` — structural consistency + cross-set backfill
5. `build_me*.py` / `generate_tcgdex_*.py` — assemble EN sideload files
