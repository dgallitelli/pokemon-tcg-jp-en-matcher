#!/usr/bin/env python3
"""
Backfill `image` (and any missing illustrator) on ME1.json + ME2.json from TCGdex.

Why: the original ME1/ME2 sideloads were built from a Serebii scrape (text) +
TCGdex backfill (data) — but image URLs were left null because neither pipeline
fetched them. The runtime falls back to Serebii via SEREBII_SLUGS, which works
but routes us through Serebii's CDN. TCGdex now hosts every card in these sets,
so we pin authoritative image URLs and keep Serebii only as a runtime fallback
for any future card TCGdex hasn't indexed yet.

Important: text fields are NOT modified. Only `image` (always set) and
`illustrator` (only when ours is missing) get touched. ME3 is intentionally
out of scope — its text was manually cleaned ({C} → "Colorless") in
enrich_m3_me3.py and a re-pull would regress that.

Run once when ME1/ME2 are first migrated; re-run after a TCGdex release that
fills in fields we still lack. Idempotent.
"""
import json
import pathlib
import time
import urllib.request
from urllib.error import URLError

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
API = "https://api.tcgdex.net/v2/en"
SETS = [("me01", "ME1"), ("me02", "ME2")]


def api_get(path):
    url = f"{API}/{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "pokemon-tcg-jp-en-matcher/me-image-migration"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except URLError as e:
            if attempt < 2:
                time.sleep(1 + attempt)
                continue
            raise RuntimeError(f"failed to fetch {url}: {e}") from e


def migrate_set(tcg_id, our_id):
    target = DATA / f"{our_id}.json"
    sideload = json.loads(target.read_text())
    cards = sideload["cards"]
    set_data = api_get(f"sets/{tcg_id}")
    brief = set_data.get("cards") or []
    print(f"\n=== {our_id} ({tcg_id}): {len(brief)} cards in TCGdex, {len(cards)} cards locally ===")

    img_added = 0
    illustrator_added = 0
    skipped_missing = 0
    for stub in brief:
        local_id = stub.get("localId") or stub["id"].split("-")[-1]
        full = api_get(f"cards/{stub['id']}")
        ours = cards.get(local_id)
        if ours is None:
            skipped_missing += 1
            print(f"  ! {our_id}-{local_id} not present locally; skipping")
            continue
        # Image: always set (source of truth for the migration).
        new_image = full.get("image")
        if new_image and ours.get("image") != new_image:
            ours["image"] = new_image
            img_added += 1
        # Illustrator: only fill when ours is missing — never overwrite.
        if not ours.get("illustrator") and full.get("illustrator"):
            ours["illustrator"] = full["illustrator"]
            illustrator_added += 1

    target.write_text(json.dumps(sideload, ensure_ascii=False, indent=2) + "\n")
    print(f"  images set: {img_added}, illustrators added: {illustrator_added}, skipped: {skipped_missing}")


def main():
    for tcg_id, our_id in SETS:
        migrate_set(tcg_id, our_id)


if __name__ == "__main__":
    main()
