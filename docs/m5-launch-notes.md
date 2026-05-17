# M5 (Abyss Eye) launch runbook

Quick reference for wiring M5 into the live app on release day. JP-only at launch.
EN sideload (ME5) is a separate task once Serebii publishes EN-language pages,
expected mid-July 2026.

## Confirmed facts

| Field | Value | Source |
|---|---|---|
| JP set code | `M5` | Serebii navigation under `/card/abysseye/` |
| Set name (romanized) | `Abyss Eye` | Serebii |
| JP release date | 2026-05-22 | Serebii |
| Main set size | 81 cards | Serebii pagination (`#1 / 81 … #81 / 81`) |
| Secret-rares count | TBD on release | — |
| Serebii slug | `abysseye` | Verified live: `https://www.serebii.net/card/abysseye/001.shtml` |
| pokemon-card.com card-ID range | TBD — run `scripts/probe_m5_id_range.py` | — |
| TCGdex JP set entry | not yet present (expected eventually) | `api.tcgdex.net/v2/ja/sets/M5` was 404 as of 2026-05-17 |
| EN equivalent (ME5) | mid-July 2026 (per release plan) | deferred |

## Release-day steps (run in order)

1. **Probe the card-ID range.**
   ```bash
   python3 scripts/probe_m5_id_range.py
   ```
   Output gives you `CARD_ID_START` and `CARD_ID_END`. If it reports "no M5
   cards found" within an hour of the official release, wait — pokemon-card.com
   sometimes publishes throughout the day. Re-run as needed.

   **Sanity check before trusting the output:** open
   `https://www.pokemon-card.com/card-search/details.php/card/<first_cid>/regu/XY`
   in a browser and confirm the page actually shows an M5 card numbered `001/...`.
   If the probe found a single match followed by immediate misses, that's a
   false positive — override the search range with `--start` / `--end` and try
   again, or pass `--match` with whatever set-name string actually appears on
   the page.

2. **Fill in the scrape script constants.** Edit `scripts/scrape_m5.py`:
   ```python
   CARD_ID_START = <value from probe>
   CARD_ID_END   = <value from probe>
   ```

3. **Scrape JP card data.**
   ```bash
   python3 scripts/scrape_m5.py
   ```
   Produces `data/M5.json`. Verify the card count matches the probe output.

4. **Add M5 to Serebii enrichment.** Edit `scripts/scrape_serebii.py` (lines
   15-23, the `SET_SLUGS` dict):
   ```python
   SET_SLUGS = {
       ...
       "M5": "abysseye",
   }
   ```
   Then run the script. Verify abilities, weakness/resistance, and attack
   effects are populated in `data/M5.json`.

5. **Wire M5 into the app.** Edit `app.js`:
   - In `SIDELOAD_CONFIG.jp` (around line 38): add
     `{ id: "M5", name: "Abyss Eye", file: "data/M5.json", cardCount: <total from data file> }`
   - In `SEREBII_SLUGS` (around line 169): add `'M5': 'abysseye',`
   - Do NOT add anything to `JP_TO_EN_SIDELOAD` yet — that's for the ME5 task.

6. **Run the test suite.**
   ```bash
   node tests/test_matcher.js
   ```
   All tests must pass before opening a PR.

7. **Manual sanity check.** Open the local site, type `M5` in the Set ID
   input, pick a card number — verify the JP panel renders with image, attacks,
   and weakness/resistance.

8. **Open the PR.** One PR containing `data/M5.json` + the `app.js` edits +
   the `scripts/scrape_serebii.py` edit. Wait for CI to pass before merging
   (project convention from `AGENTS.md`).

## Non-goals on release day

- ME5 EN sideload — defer until Serebii publishes EN pages (~mid-July 2026).
- Adding M5 to `JP_TO_EN_SIDELOAD` — not until the ME5 sideload exists.
- TCGdex JP set integration — TCGdex will list M5 on its own schedule; the
  sideload path takes over for any set in `SIDELOAD_CONFIG.jp`, so no action
  is required.
