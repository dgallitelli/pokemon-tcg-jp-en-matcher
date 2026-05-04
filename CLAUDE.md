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

**Serebii image slugs** (used in `sideloadImageUrl()` via `SEREBII_SLUGS`):
- M1S → megasymphonia, M1L → megabrave, M2 → infernox
- M3 → nihilzero, M4 / ME4 → ninjaspinner
- ME1 → megaevolution, ME2 → phantasmalflames, ME3 → perfectorder
- M2a / ME2a → megadreamex (Serebii has no dedicated EN page; ME2a reuses the JP slug — numbering is identical)

**JP image fallback:** `renderCard(card, lang, badge, score, fallbackImgUrl)` accepts an optional 5th arg. When the EN `<img>` fails to load (e.g. Serebii 404, or a new card not yet on their site), the `onerror` handler swaps `src` to `fallbackImgUrl`, adds a `.jp-fallback` dashed outline, and reveals a "Showing Japanese card" hint. Call sites pass `cardImageUrl(jpCard)` as the fallback.

## Key invariants

- **JP image as EN fallback only if EN image is truly unavailable.** The EN panel always *tries* its own Serebii image first; the JP image is only swapped in by `onerror` when that fails. When the JP image is showing in the EN panel, it must be visually marked (`.jp-fallback` dashed outline + hint text) so the user knows they're looking at the JP version.
- **Never show JP text in the EN panel.** Effect text is validated with `isEnglish()` — any text containing Japanese unicode (U+3040–9FFF) is rejected. If attack names weren't translated (synthetic EN cards), render them as `—`.
- **Trainer name matching within translation sideloads** uses `TRAINER_NAME_MAP` first (most precise), then illustrator as a fallback only when unambiguous (exactly one candidate). The map keys must match the ME set card names exactly — these sometimes differ from TCGdex standard names (e.g. "Strange Timepiece" not "Spooky Watch", "Fighting Gong" not "Fight Gong").
- All EN sideloads are pre-fetched at startup (needed for cross-set dexId scanning in step 2b of `doSearch`). JP sideloads are lazy-loaded on first access.
- Sideload set ID lookups are case-insensitive: `SIDELOAD_JP_CONFIG` keys and `JP_TO_EN_SIDELOAD` lookups use `.toUpperCase()`. The store key in `SIDELOAD_SETS` matches `setUpper` (not `cfg.id`), so mixed-case IDs like `M2a` work correctly.
- EN sideload cards have `id` and `set` fields injected on load (older files like ME1/ME2 predate these fields).

## Known limitations

- **M2a**: no EN sideload — relies entirely on TCGdex API live matching. All 193 Pokemon cards now have `dexId` (patched via `scripts/patch_m2a_dexids.py`). Cards with no TCGdex match show "No English equivalent found."
- Sets not in TCGdex and without a sideload (e.g. `sPD`, XY-era promo decks) cannot be searched.

## Data pipeline scripts

Run manually when new sets release:
1. `scrape_m*.py` — scrape JP card data from pokemon-card.com
2. `fetch_tcgdex_en.py` — fetch EN data from TCGdex and backfill JP attack text (covers M1S, M1L, M2; extend for new sets)
3. `scrape_serebii.py` — enrich with weakness/resistance/abilities from Serebii
4. `normalize_data.py` — structural consistency + cross-set backfill (covers M1S–M4; extend for new sets)
5. `build_me*.py` / `generate_tcgdex_*.py` — assemble EN sideload files
6. `patch_m2a_dexids.py` — one-time patch; re-run if M2a ex cards are added

**When adding a new JP sideload set:**
1. Add entry to `SIDELOAD_CONFIG.jp` in `index.html` (id must be consistent casing; lookup is uppercased automatically)
2. Add Serebii slug to `SEREBII_SLUGS` in `app.js` (for both the JP set and its EN counterpart if they have separate Serebii pages)
3. Add JP→EN mapping to `JP_TO_EN_SIDELOAD` if an EN translation sideload exists
4. Add EN sideload TRAINER_NAME_MAP entries using the exact ME-set card names (not TCGdex standard names)
