# Mobile-first UX redesign — JP→EN Matcher

**Date:** 2026-05-04
**Status:** Approved, pre-implementation

## Context

The tool is used mid-game: the player looks at a JP card in hand and needs to quickly see its English equivalent on their phone. Today's UI treats the JP and EN panels as equals (side-by-side, same size, same content depth). The user's actual workflow is asymmetric — the EN card is the answer, the JP card is already in their hand and only needs a quick "yes, that's the one I typed" confirmation.

This redesign reorients the UI around that priority while bundling in the already-fixed (but not yet pushed) image-loading bug for M1L/M1S/M2/M2a.

## Guiding principle

**EN first, JP as confirmation.** EN content is the primary visual; JP is secondary and compact. On mobile, EN renders first (above the fold when possible); JP follows. On desktop, side-by-side is preserved since screen real estate is plentiful.

## Non-goals

- No changes to matching logic, scoring, or data pipeline.
- No changes to how sideload data is loaded.
- No PWA/offline/installability work.
- No changes to the browse-set grid's internal layout (only its entry-point button).
- No desktop layout overhaul — desktop largely keeps current behavior.

## Design

### 1. Layout

**Mobile (viewport < 680px):** vertical stack, EN-first.

1. **EN panel** (full width)
   - EN image, large (tap → fullscreen modal, unchanged from today)
   - Card name + set badge
   - Attacks/abilities always visible
   - "Show details ▾" collapsible for meta (HP, stage, illustrator, weakness, resistance, retreat, flavor)
2. **JP confirmation block** (below EN)
   - JP image only, ~60% viewport width, centered
   - "Show JP text ▾" link below → expands compact JP attacks/abilities block (no meta)

**Desktop (viewport ≥ 680px):** side-by-side, unchanged from today. Both panels show image + attacks; "Show details ▾" reveals meta.

**Special case — JP-fallback image (EN Serebii URL 404s → reuses JP image):** single merged panel.

- One image at top with `.jp-fallback` dashed outline
- "🔄 English translation" badge + card name (English)
- EN attacks/abilities below
- Italic note: "Showing Japanese card art — no English print available yet"
- "Show details ▾" at bottom
- No separate JP panel

**Special case — synthetic EN (no image, translated text):** normal two-panel layout. EN panel's image area shows a "No English image yet" stub; attacks/text are the focus.

### 2. Input controls

**Mobile:**

- Initial state (no result showing): input block in normal document flow under the header.
- Result-showing state: input block becomes a **sticky bottom bar** (≈56px tall).
  - Contents: Set ID pill (current value, tappable) · Card # input (narrow, numeric keypad) · Match button · 📂 Browse icon
  - Tapping the Set ID pill expands the sticky bar vertically to reveal the full Set ID input + recents/autocomplete chip row; collapses back to the pill after selection.
  - Sticky bar auto-hides when scrolling *up* past the EN image (so it doesn't obscure the card), reappears on scroll down.

**Desktop:**

- Input block stays at the top, no sticky behavior. Similar to today.

**Shared (both platforms):**

- **Recents chips** under Set ID input: single horizontally-scrollable row of the last 5 set IDs used, persisted in localStorage as a ring buffer (`recentSets`, bounded to 5, most-recent first).
  - Tap a chip → Set ID input populates + field blurs + focus moves to Card #.
  - If localStorage is empty (first-time user), the chip row is not rendered (0 height, no layout shift).
- **Autocomplete chips** swap in when Set ID input is focused and non-empty: up to 3 live-matched set IDs from TCGdex + sideload sets (case-insensitive substring match on the ID). Recents return when input is blurred with a value or emptied.
- **Browse set** button: secondary button (gold-outlined, not filled) adjacent to Match on desktop; compact 📂 icon on mobile sticky bar. Opens the existing browse grid for the currently-typed set ID.
- **Prev/Next navigation removed** from the results area entirely.

**Keyboard behavior:**

- Set ID input: `autocapitalize="characters"` so "sv8a" visually becomes "SV8A" while typing on mobile.
- Card # input: unchanged — `inputmode="numeric"`, pads leading zeros.
- Enter in Card # → Match (unchanged).
- Enter in Set ID → move focus to Card # (change from today's "triggers Match"). Rationale: users always type both fields; moving focus avoids premature search on incomplete input.

### 3. Results rendering

**EN panel (with image):**

- Image (tappable, opens modal)
- Header: name (large) + "Set · ID" line
- Confidence pip for low matches (existing logic)
- "Show details ▾" collapsible: HP, stage, illustrator, weakness, resistance, retreat, flavor
- Attacks/abilities always visible
- Share button (🔗 icon) in the panel header row, right-aligned

**EN panel (no image / synthetic / no match):**

- Header with name + small "No English image yet" stub
- Attacks/abilities/effects always visible
- "Show details ▾" for meta
- The current "This card has no official English print yet" note moves inside the panel (not a separate strip)

**JP panel (mobile, below EN):**

- Image only by default, ~60% viewport width, centered
- "Show JP text ▾" link below image → expands compact attacks/abilities block (no meta)

**JP panel (desktop, side-by-side):**

- Image + attacks/abilities visible
- "Show details ▾" for meta (visual symmetry with EN panel)

**JP fallback merged panel** (see section 1 for layout):

- Used when the EN image 404s and we fall back to the JP image
- No separate JP panel rendered alongside it

**Wrong-card flow:** unchanged. Button sits below EN panel on desktop, above the sticky bar on mobile.

**Share link:** moves from below the cards into the EN panel header as a 🔗 icon button. Copy-to-clipboard behavior unchanged.

### 4. Data-shape & state additions

- `localStorage.recentSets`: JSON array of up to 5 set IDs (most-recent first). Updated on every successful search. Existing `lastSet` key retained for backward compatibility and initial input restoration.
- No new globals in `app.js` beyond what's needed to track the details-toggle open/closed state (handled via a CSS class on the panel, no JS state).

### 5. CSS strategy

- Mobile stacking: reorder via `flex-direction: column` + `order` properties on `.cards-container` children, triggered by the existing `@media (max-width: 680px)` block.
- Sticky bar: new `.input-bar--sticky` class applied to the input section on mobile when `#results` contains children.
- Details toggle: `<details>` native HTML element. Closed by default. Summary is styled as a subtle "Show details ▾" link.
- Chip row: `.chip-row` with `overflow-x: auto` + `scrollbar-width: none`. Chips are 44px min tap target.
- JP-fallback merged panel: new `.card-panel--merged` class, rendered instead of the usual pair.

### 6. File structure

All changes are contained to three existing files:

- `index.html` — updated input section markup (chip row containers, browse button next to match), minor semantic tweaks.
- `style.css` — new classes, updated `@media (max-width: 680px)` block.
- `app.js`:
  - `recentSets` read/write helpers
  - Chip rendering function
  - Updated `renderCard()` signature: add a `compact` flag for JP-on-mobile variant and a `merged` variant for the fallback case
  - Sticky-bar show/hide on scroll (IntersectionObserver on EN image, not scroll listener)
  - Remove `renderNavRow()` and its call sites

No new files, no new dependencies.

### 7. Testing

**Device/viewport matrix (manual, via chrome-devtools MCP):**

- iPhone-sized viewport (375×812) — verify stacking, sticky bar, scroll-hide behavior
- Tablet (768×1024) — verify switch-over to side-by-side near breakpoint
- Desktop (1280×800) — verify unchanged layout

**Scenario matrix:**

- JP card with full EN match (SV5a/051 Snorlax — TCGdex path)
- JP card with sideload EN match, EN image available (M1S/001, M1L/001, M2/001, M2a/001 — all four sets previously broken)
- JP card with sideload EN match, EN image 404 (simulate by forcing a bad `src`)
- JP card with synthetic EN translation (ME1 card missing from Serebii range — edge case)
- JP card with no English equivalent found at all
- Set ID input with recents chips populated
- Set ID input autocomplete suggestions
- Browse set button from sticky bar

**What "done" looks like:**

- All four previously-broken sets (M1S/M1L/M2/M2a) load EN images.
- Mobile viewport: EN panel visible without scrolling when image is available.
- Sticky input bar appears during result view, disappears on initial page.
- Chip row persists recents across page reloads.
- No regressions on SV5a/051 or other TCGdex-path searches.
- No layout shift on initial page load.

## Out-of-scope / deferred

- Offline support / PWA install.
- Prev/next set navigation (removed per user request).
- Dark/light mode toggle.
- Translation confidence tuning.
- Data pipeline changes.

## Rollout

Two commits on `main`:

1. **Image fix** (already in working tree, needs commit + push) — `SEREBII_SLUGS` table, JP fallback mechanism, doc updates.
2. **UX redesign** — this spec's implementation.

Both pushed together. GitHub Pages will pick up automatically.
