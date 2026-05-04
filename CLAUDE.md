# Pokémon TCG JP→EN Matcher

## Platform goal

Mobile-first quick reference tool for playing Pokémon TCG with Japanese cards.
The user looks up a JP card mid-game and needs the English equivalent instantly —
held up to opponents as proof of what the card does.

**Display priority:**
1. **EN first, JP confirms.** The EN panel is the primary answer; the JP panel exists to confirm the user typed the correct card.
2. If an official English card image is available → show it large (the EN card panel is what you show opponents).
3. If no English image is available → show English translated text. Attack names may be `—` for synthetic cards.

**Layout:**
- **Desktop (≥ 681px):** side-by-side (JP left, arrow, EN right). Meta (HP/stage/illustrator/etc) is in a native `<details>` toggle, auto-opened on desktop.
- **Mobile (< 681px):** vertical stack, EN on top (full width), compact JP confirmation block below (image-only by default, "Show JP text" reveals attacks). No arrow. Details collapsed by default.
- **JP-fallback merged panel:** when the EN image URL equals the JP image URL (e.g. ME2a reuses the `megadreamex` slug), render a single merged panel instead of two with a "Showing Japanese card art" note.

## Architecture

Single `index.html` + `style.css` + `app.js` — no build step, no dependencies, deploys as a GitHub Pages static site.

**Data sources:**
- `data/M*.json` — JP sideload sets scraped from pokemon-card.com
- `data/ME*.json` — EN translation sideloads built from TCGdex API + Serebii scraping
- TCGdex API (`https://api.tcgdex.net/v2`) — live lookup for standard sets

**Mobile-first UX:**
- Input section becomes a fixed sticky bottom bar when results are showing (mobile only). Controlled by `.input-section--sticky` class set by `refreshStickyBar()` in `app.js`.
- The sticky bar auto-hides (`.input-section--hidden`) while the EN image is >70% visible, via `IntersectionObserver`.
- Recents chips (`#chipRow`) show the last 5 set IDs searched (localStorage `recentSets`); autocomplete chips replace them while the Set ID input is focused + non-empty.
- Meta rows hide behind native `<details>` "Show details" toggles. `openDetailsOnDesktop()` auto-opens them on desktop after each render (it also calls `refreshStickyBar()`).
- Share link is a 🔗 icon in the EN panel header. Previously a standalone button below the cards.
- Prev/next navigation was removed. Mid-game use is almost always a fresh lookup; the sticky bar keeps the input reachable.

**JP→EN sideload mapping:**
- M1S / M1L → ME1 (Mega Evolution)
- M2 → ME2 (Phantasmal Flames)
- M3 → ME3 (Perfect Order)
- M4 → ME4 (Ninja Spinner)
- M2a → ME2a (Destined Rivals / sv10) — authoritative TCGdex data, not a Serebii translation. Built by `scripts/build_me2a_from_tcgdex.py`.

**Serebii image slugs** (used in `sideloadImageUrl()` via `SEREBII_SLUGS`):
- M1S → megasymphonia, M1L → megabrave, M2 → infernox
- M3 → nihilzero, M4 / ME4 → ninjaspinner
- ME1 → megaevolution, ME2 → phantasmalflames, ME3 → perfectorder
- M2a → megadreamex, ME2a → destinedrivals
- Note: ME2a cards pull images from TCGdex (`assets.tcgdex.net/en/sv/sv10/...`) set directly on the card `image` field. Serebii only kicks in as an `onerror` fallback.

**JP image fallback:** `renderCard(card, lang, badge, score, fallbackImgUrl)` accepts an optional 5th arg. When the EN `<img>` fails to load (e.g. Serebii 404, or a new card not yet on their site), the `onerror` handler swaps `src` to `fallbackImgUrl`, adds a `.jp-fallback` dashed outline, and reveals a "Showing Japanese card" hint. Call sites pass `cardImageUrl(jpCard)` as the fallback.

## Key invariants

- **EN first on mobile.** The stacking order on mobile must always be EN panel → compact JP block. Never reverse. The compact JP renderer (`renderCardCompactJp`) is used only on mobile; desktop uses the regular `renderCard` for both panels.
- **JP image as EN fallback only if EN image is truly unavailable.** The EN panel always *tries* its own Serebii image first; the JP image is only swapped in by `onerror` when that fails. When the JP image is showing in the EN panel, it must be visually marked (`.jp-fallback` dashed outline + hint text) so the user knows they're looking at the JP version.
- **Merged panel on same-image case.** When `cardImageUrl(jpCard) === cardImageUrl(enCard)` (which happens for ME2a since it shares the `megadreamex` slug with M2a), `assembleResults` returns a single panel with a "Showing Japanese card art — no English print available yet" note. No separate JP panel.
- **Never show JP text in the EN panel.** Effect text is validated with `isEnglish()` — any text containing Japanese unicode (U+3040–9FFF) is rejected. If attack names weren't translated (synthetic EN cards), render them as `—`.
- **Trainer name matching within translation sideloads** uses `TRAINER_NAME_MAP` first (most precise), then illustrator as a fallback only when unambiguous (exactly one candidate). The map keys must match the ME set card names exactly — these sometimes differ from TCGdex standard names (e.g. "Strange Timepiece" not "Spooky Watch", "Fighting Gong" not "Fight Gong").
- All EN sideloads are pre-fetched at startup (needed for cross-set dexId scanning in step 2b of `doSearch`). JP sideloads are lazy-loaded on first access.
- Sideload set ID lookups are case-insensitive: `SIDELOAD_JP_CONFIG` keys and `JP_TO_EN_SIDELOAD` lookups use `.toUpperCase()`. The store key in `SIDELOAD_SETS` matches `setUpper` (not `cfg.id`), so mixed-case IDs like `M2a` work correctly.
- EN sideload cards have `id` and `set` fields injected on load (older files like ME1/ME2 predate these fields).

## Known limitations

- Sets not in TCGdex and without a sideload (e.g. `sPD`, XY-era promo decks) cannot be searched.

## Source attribution

Every EN panel shows a "SOURCE:" line, inferred from the card ID prefix in `sourceAttribution()`:
- `ME2a` → "TCGdex · Destined Rivals" (authoritative)
- `ME1/ME2/ME3/ME4` → "Serebii + TCGdex" (machine-translated, best-effort)
- Synthetic cards (attack name `—`) → "Serebii (machine-translated)"
- Live TCGdex match (e.g. `sv06-136`) → "TCGdex"

EN panels also include a "View on Limitless ↗" link when `limitlessLinkFor()` can map the set ID to a Limitless set code (see `LIMITLESS_SET_MAP`). Unmapped sets get no link rather than a broken 404.

## Data pipeline scripts

Run manually when new sets release:
1. `scrape_m*.py` — scrape JP card data from pokemon-card.com
2. `fetch_tcgdex_en.py` — fetch EN data from TCGdex and backfill JP attack text (covers M1S, M1L, M2; extend for new sets)
3. `scrape_serebii.py` — enrich with weakness/resistance/abilities from Serebii
4. `normalize_data.py` — structural consistency + cross-set backfill (covers M1S–M4; extend for new sets)
5. `build_me*.py` / `generate_tcgdex_*.py` — assemble EN sideload files
6. `patch_m2a_dexids.py` — one-time patch; re-run if M2a ex cards are added

**When adding a new JP sideload set:**
1. Add entry to `SIDELOAD_CONFIG.jp` in `app.js` (id must be consistent casing; lookup is uppercased automatically)
2. Add Serebii slug to `SEREBII_SLUGS` in `app.js` (for both the JP set and its EN counterpart if they have separate Serebii pages)
3. Add JP→EN mapping to `JP_TO_EN_SIDELOAD` if an EN translation sideload exists
4. Add EN sideload TRAINER_NAME_MAP entries using the exact ME-set card names (not TCGdex standard names)
