#!/usr/bin/env python3
"""Probe pokemon-card.com to find M5 (Abyss Eye)'s contiguous numeric card-ID range.

Read-only. Prints the first/last IDs and the suggested CARD_ID_START / CARD_ID_END
values for scripts/scrape_m5.py. Does not modify any files.

Usage:
    python3 scripts/probe_m5_id_range.py
    python3 scripts/probe_m5_id_range.py --start 50205 --end 50500
    python3 scripts/probe_m5_id_range.py --match "アビスアイ"
"""
import argparse
import re
import sys
import urllib.request
import urllib.error

BASE_URL = "https://www.pokemon-card.com/card-search/details.php/card/{}/regu/XY"

# Default markers we expect to see on an M5 card page.
# Any one match is enough (the page may render either romanized or JP form).
# IMPORTANT: the existing scrape scripts don't extract set names, so we haven't
# verified empirically which form pokemon-card.com renders for M5. On release
# day, eyeball one card page in the browser and pass --match if needed.
DEFAULT_MARKERS = ["Abyss Eye", "アビスアイ"]

# Minimum NNN/NNN denominator we'll accept as "looks like M5".
# Main set is 81; secret rares push the total higher. This is a coarse filter —
# other recent sets (M3=117, M4=120, M2a=193) also exceed 81, so the marker
# string match above is what actually discriminates M5 from neighbors.
DEFAULT_MIN_DENOMINATOR = 81


def fetch(card_id, timeout=15):
    """Fetch a card detail page; return (status, body) or (None, None) on error."""
    url = BASE_URL.format(card_id)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (M5 probe)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return None, None


def looks_like_m5(html, markers, min_denominator):
    """Return (is_m5, card_num, denominator) for a fetched page body."""
    if not html:
        return False, None, None
    if not any(marker in html for marker in markers):
        return False, None, None
    num_m = re.search(r'&nbsp;(\d+)&nbsp;/&nbsp;(\d+)&nbsp;', html)
    if not num_m:
        return False, None, None
    card_num = int(num_m.group(1))
    denominator = int(num_m.group(2))
    if denominator < min_denominator:
        return False, card_num, denominator
    return True, card_num, denominator


def find_first_match(start, end, markers, min_denominator, max_probes):
    """Walk forward from `start` until we find the first M5 card or hit `end`/`max_probes`."""
    probes = 0
    for cid in range(start, end + 1):
        if probes >= max_probes:
            print(f"  → reached --max-probes={max_probes}, stopping search for first match")
            return None, None, None
        probes += 1
        status, body = fetch(cid)
        is_m5, card_num, denom = looks_like_m5(body, markers, min_denominator)
        marker_hit = "M5" if is_m5 else ("?" if body else "·")
        print(f"  probe {cid}: status={status} {marker_hit}")
        if is_m5:
            return cid, card_num, denom
    return None, None, None


def find_last_contiguous(first_cid, end, markers, min_denominator, gap, max_probes):
    """From `first_cid`, walk forward until we see `gap` consecutive non-M5 pages."""
    last_match = first_cid
    consecutive_misses = 0
    probes = 0
    for cid in range(first_cid + 1, end + 1):
        if probes >= max_probes:
            print(f"  → reached --max-probes={max_probes}, stopping forward walk")
            break
        probes += 1
        status, body = fetch(cid)
        is_m5, card_num, denom = looks_like_m5(body, markers, min_denominator)
        if is_m5:
            last_match = cid
            consecutive_misses = 0
            print(f"  walk+ {cid}: status={status} M5 (#{card_num}/{denom})")
        else:
            consecutive_misses += 1
            print(f"  walk+ {cid}: status={status} miss ({consecutive_misses}/{gap})")
            if consecutive_misses >= gap:
                break
    return last_match


def find_first_contiguous(first_cid, lower_bound, markers, min_denominator, gap, max_probes):
    """From `first_cid`, walk backward until we see `gap` consecutive non-M5 pages.
    Defends against pokemon-card.com publishing IDs out of order — the first match
    we found going forward might not actually be card #001."""
    earliest_match = first_cid
    consecutive_misses = 0
    probes = 0
    for cid in range(first_cid - 1, lower_bound - 1, -1):
        if probes >= max_probes:
            print(f"  → reached --max-probes={max_probes}, stopping backward walk")
            break
        probes += 1
        status, body = fetch(cid)
        is_m5, card_num, denom = looks_like_m5(body, markers, min_denominator)
        if is_m5:
            earliest_match = cid
            consecutive_misses = 0
            print(f"  walk- {cid}: status={status} M5 (#{card_num}/{denom})")
        else:
            consecutive_misses += 1
            print(f"  walk- {cid}: status={status} miss ({consecutive_misses}/{gap})")
            if consecutive_misses >= gap:
                break
    return earliest_match


def main():
    parser = argparse.ArgumentParser(description="Probe pokemon-card.com for M5's card-ID range")
    parser.add_argument("--start", type=int, default=50205, help="numeric card ID to start probing (default: 50205, just past M4's end at 50204)")
    parser.add_argument("--end",   type=int, default=None,  help="numeric card ID to stop probing at (default: start+200)")
    parser.add_argument("--match", action="append", default=None, help="set-name marker to look for in HTML (repeatable)")
    parser.add_argument("--gap",   type=int, default=5,     help="consecutive non-matching IDs that end the contiguous range (default: 5)")
    parser.add_argument("--min-denominator", type=int, default=DEFAULT_MIN_DENOMINATOR, help="minimum NNN/NNN denominator to accept (default: 81)")
    parser.add_argument("--max-probes", type=int, default=250, help="hard cap on total probe requests (default: 250)")
    args = parser.parse_args()

    end = args.end if args.end is not None else args.start + 200
    markers = args.match if args.match else DEFAULT_MARKERS

    print(f"Probing for M5 in [{args.start}..{end}], markers={markers}, min_denom={args.min_denominator}, gap={args.gap}, max_probes={args.max_probes}")
    print("Step 1: find first M5 card")
    first_cid, first_num, first_denom = find_first_match(args.start, end, markers, args.min_denominator, args.max_probes)
    if first_cid is None:
        print("\nNo M5 cards found in the searched range.")
        print("If the set hasn't been published yet, wait and re-run.")
        print("If you suspect a different range, use --start / --end.")
        sys.exit(1)

    print(f"\nFirst M5 hit: numeric ID {first_cid} → set card #{first_num}/{first_denom}")

    print("\nStep 2: walk backward to confirm we're at card 001 (defends against out-of-order publishing)")
    earliest_cid = find_first_contiguous(first_cid, args.start, markers, args.min_denominator, args.gap, args.max_probes)

    print("\nStep 3: walk forward to find the end of the contiguous range")
    last_cid = find_last_contiguous(first_cid, end, markers, args.min_denominator, args.gap, args.max_probes)

    total = last_cid - earliest_cid + 1
    print("\n" + "=" * 60)
    print(f"M5 first card ID: {earliest_cid}")
    print(f"M5 last card ID:  {last_cid}")
    print(f"Total: {total} cards")
    print("→ Edit scripts/scrape_m5.py:")
    print(f"      CARD_ID_START = {earliest_cid}")
    print(f"      CARD_ID_END   = {last_cid}")
    print("=" * 60)


if __name__ == "__main__":
    main()
