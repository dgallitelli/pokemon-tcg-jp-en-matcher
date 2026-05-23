# SV6a (Night Wanderer) sideload runbook

Quick reference for adding a JP sideload for SV6a (ナイトワンダラー / Night Wanderer)
so the app stops 404'ing on cards from this set. TCGdex registers SV6a but ships
the `cards` array empty, so without a sideload every `/ja/cards/sv6a-NNN` lookup
returns 404 and the user sees `❌ Card not found: sv6a-001`.

This follows the same pipeline as M1S–M5: scrape pokemon-card.com → backfill EN
text from TCGdex → enrich with Serebii → normalize → register in `app.js`.

## Confirmed facts

| Field | Value | Source |
|---|---|---|
| JP set code | `SV6a` | TCGdex `/ja/sets/SV6a` (registered, but `cards` is empty) |
| JP set name | `ナイトワンダラー` (Night Wanderer) | pokemon-card.com `/products/sv/sv6a.html`, Serebii title |
| JP release date | 2024-06-07 | TCGdex set entry |
| Main set size | 64 cards | Serebii pagination on `nightwanderer/001.shtml` (`1/64`) |
| Total cards (incl. secret rares) | 94 cards (#1–64 main, #65–94 SAR/UR/IR) | confirmed via probe |
| pokemon-card.com expansion code | `SV6a` | confirmed live at `?expansionCodes=SV6a` |
| pokemon-card.com `pg` index | `917` (label "強化拡張パック「ナイトワンダラー」") | embedded in `index.php?pg=917` page metadata |
| pokemon-card.com card-id ranges | `45876–45939` (#1–64) and `46042–46071` (#65–94) — non-contiguous | confirmed via `scripts/probe_sv6a_id_range.py` |
| Serebii slug | `nightwanderer` | verified live: `https://www.serebii.net/card/nightwanderer/001.shtml` |
| EN equivalent in TCGdex | `sv06.5` (Shrouded Fable, 99 cards) | TCGdex `/en/sets/sv06.5` |
| EN reprint coverage | first 64 cards of sv06.5 mirror SV6a #1–64 (e.g. SV6a-001 Joltik = sv06.5-001) | spot-check via TCGdex |

## Why this is a JP sideload only — no ME6a

Unlike M1S/M2/M3/M4 (Mega-era JP-only sets that need a hand-rolled EN
translation file via Serebii), SV6a's English counterpart **already lives in
TCGdex** as `sv06.5` (Shrouded Fable). The existing matcher path (`doSearch`
step 2b in `app.js`) does dexId-based name lookup and then scores TCGdex EN
candidates — it will find the correct sv06.5 card automatically once SV6a JP
cards have `dexId` populated.

So:

- **Build:** `data/SV6a.json` (JP sideload only).
- **Don't build:** `data/ME6a.json` — `JP_TO_EN_SIDELOAD` does not get an entry
  for SV6a. Falling through to the live TCGdex EN path is correct.
- **TRAINER_NAME_MAP:** SV6a's trainer cards are reprints of sv6 (Twilight
  Masquerade) plus a few new ones; most are already mapped. Audit after the
  scrape — see step 5.

## Release-day steps

1. **Create the probe script.** Copy `scripts/probe_m5_id_range.py` to
   `scripts/probe_sv6a_id_range.py` and adjust the constants at the top:
   ```python
   DEFAULT_MARKERS         = ["ナイトワンダラー", "Night Wanderer"]
   DEFAULT_MIN_DENOMINATOR = 64
   parser.add_argument("--start", type=int, default=42000, ...)
   parser.add_argument("--end",   type=int, default=None, ...)  # default start+6000
   ```
   The wider default range reflects that SV6a sits in the older, denser
   pre-M-series part of pokemon-card.com (2024), not the contiguous 50000+
   block where M1–M5 live.

2. **Probe the card-ID range.**
   ```bash
   python3 scripts/probe_sv6a_id_range.py
   ```
   Expected output: `CARD_ID_START` and `CARD_ID_END` covering 64–~80 IDs.
   If the probe finds nothing in 42000–48000, widen with `--start 38000
   --end 48000`. If it returns a single hit followed by misses, that's a
   non-SV6a card whose page text happens to mention Night Wanderer — re-run
   with `--match 強化拡張パック「ナイトワンダラー」` for stricter matching.

   Sanity check the probe output by opening
   `https://www.pokemon-card.com/card-search/details.php/card/<first_cid>/regu/XY`
   and confirming the page shows an SV6a card numbered `001/64`.

3. **Create and run the JP scrape script.** Copy `scripts/scrape_m5.py` to
   `scripts/scrape_sv6a.py` and adjust the constants at the top:
   ```python
   SET_ID    = "SV6a"
   SET_NAME  = "Night Wanderer"
   CARD_ID_START = <value from probe>
   CARD_ID_END   = <value from probe>
   ```
   And the output path at the bottom:
   ```python
   out_path = "data/SV6a.json"
   ```
   And the release date in the assembled `data` dict:
   ```python
   "releaseDate": {"ja": "2024-06-07"},
   ```
   Then run:
   ```bash
   python3 scripts/scrape_sv6a.py
   ```
   Expected: `data/SV6a.json` with 64+ cards. Any "attacks still missing
   cost" warnings at the end go on the to-fix list for step 5.

4. **Backfill EN text and dexId from TCGdex.** Edit
   `scripts/fetch_tcgdex_en.py` to add `SV6a` to the list of sets it
   processes (look for the sets array near the top). Then run it. The script
   maps SV6a JP cards to sv06.5 EN cards by dexId + illustrator and copies
   English attack/effect text into the JP card record. After this step,
   `data/SV6a.json` Pokemon cards will have `dexId` populated — that's what
   makes the matcher path work without a hand-rolled `ME6a`.

5. **Enrich with Serebii.** Edit `scripts/scrape_serebii.py` (around line 15,
   the `SET_SLUGS` dict):
   ```python
   SET_SLUGS = {
       ...
       "SV6a": "nightwanderer",
   }
   ```
   Then run it. Verify weakness/resistance, abilities, and attack effects are
   populated. For trainer cards, audit the names against `TRAINER_NAME_MAP`
   in `app.js` — anything unmapped will fall through to illustrator-only
   matching and may pick the wrong card. Expected new entries (verify
   against the scraped data):
   - any SV6a-exclusive trainers not already covered by the sv06 / Twilight
     Masquerade mappings.

6. **Normalize.** Edit `scripts/normalize_data.py` to include `SV6a` in its
   processed set list. Run it. This step deduplicates dexIds, fixes stage
   strings, and cross-set-backfills any remaining gaps.

7. **Wire SV6a into the app.** Edit `app.js`:
   - In `SIDELOAD_CONFIG.jp` (around line 39): add
     ```js
     { id: "SV6a", name: "Night Wanderer", file: "data/SV6a.json", cardCount: <total from data file> }
     ```
   - In `SEREBII_SLUGS` (around line 169): add `'SV6A': 'nightwanderer',`
     **(uppercase key — the lookup in `sideloadImageUrl` matches case-sensitively
     against the prefix returned by the regex, but `SIDELOAD_JP_CONFIG` is
     keyed with `.toUpperCase()`. Use uppercase for the slug map too so it
     works for both `SV6a` and `sv6a` user input).** Sanity-check this against
     how `M2a` is handled (which works because `M2a` itself appears verbatim
     as a key — re-test SV6a with both casings before claiming it works).
   - Do NOT add anything to `JP_TO_EN_SIDELOAD` — see "no ME6a" rationale above.
   - Do NOT add anything to `LIMITLESS_SET_MAP` for `SV6a` — the JP set has no
     Limitless code. The EN reprint mapping `'sv06.5': 'SFA'` is already there,
     so the EN candidate panel will get a Limitless link automatically.

8. **Add tests.** Per AGENTS.md "every behavioral fix adds a test":
   - In `tests/test_matcher.js`, add SV6a-specific cases: spot-check trainer
     name mappings introduced in step 5; assert SEREBII_SLUGS resolves
     `SV6A-001` to `nightwanderer/1.jpg`.
   - In `tests/test_tcgdex.js`, add an integration case asserting
     `('SV6a', '1', 'Joltik', 'sv6a JP card matches sv06.5 EN reprint by dexId')`
     so a regression in the dexId match path is caught at CI time.

9. **Run the test suite.**
   ```bash
   node tests/test_matcher.js && node tests/test_tcgdex.js
   ```
   All tests must pass before opening a PR.

10. **Manual sanity check.** `python3 -m http.server 8765` then open the local
    site and verify:
    - `SV6a` + `1` → JP panel renders Joltik (image, attacks, weakness/resistance)
      and the EN panel pairs to sv06.5-001 Joltik with a high match score.
    - `SV6a` + `64` → last main-set card pairs correctly.
    - A trainer card (numbers vary per scrape; check after step 3) → EN panel
      uses the right TRAINER_NAME_MAP entry, not an unrelated card.
    - On mobile (390×844 via chrome-devtools MCP), EN panel above the compact
      JP block, sticky bar visible.

11. **Open the PR.** One PR containing `data/SV6a.json` + the four script
    edits (probe, scrape, fetch_tcgdex_en, scrape_serebii, normalize) + the
    `app.js` edits + the test additions. Wait for CI to pass before merging
    (project convention).

## Non-goals on launch day

- **No ME6a sideload.** sv06.5 (Shrouded Fable) on TCGdex covers it. If a
  specific SV6a card scores poorly against its sv06.5 counterpart, fix the
  scoring or the TRAINER_NAME_MAP entry — don't reach for a hand-rolled EN
  file.
- **No backfill of pre-SV-era empty TCGdex sets** (XY, SM, S-series). Those
  remain unsearchable; users see the live "card not found" 404. Out of scope
  for this task.
- **No retroactive renumbering** if pokemon-card.com publishes a secret-rare
  card later than the main set. Re-run `scrape_sv6a.py` with an extended
  `CARD_ID_END` and re-PR; SV6a is small enough that the rebuild is cheap.

## Validation checklist (before merging)

- [ ] `data/SV6a.json` exists and contains ≥ 64 cards.
- [ ] Every Pokemon card in `data/SV6a.json` has a `dexId` array (otherwise
      the matcher's TCGdex EN path can't find the sv06.5 reprint).
- [ ] Every Pokemon card has `weakness`, `retreat`, and at least one attack
      with a non-empty `cost` (use the warning section emitted by
      `scrape_sv6a.py`).
- [ ] Every Trainer/Energy card has either a `TRAINER_NAME_MAP` entry or an
      effect string that's already in English (post `fetch_tcgdex_en.py`).
- [ ] `node tests/test_matcher.js` passes including the new SV6a cases.
- [ ] `node tests/test_tcgdex.js` passes including the SV6a→sv06.5 dexId case.
- [ ] Local visual check on mobile + desktop, both `SV6a` and `sv6a` casings.
