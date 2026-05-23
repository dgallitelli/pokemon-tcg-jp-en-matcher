#!/usr/bin/env python3
"""Probe pokemon-card.com to find SV6a (Night Wanderer)'s contiguous numeric card-ID range.

SV6a was released 2024-06-07, so its card IDs sit in the older / pre-M-series
section of pokemon-card.com (well below M2a's 48523 and M4's 50085). The
released-set marker we look for is the literal JP set name "ナイトワンダラー"
appearing on each card detail page.

Read-only. Prints the first/last IDs and the suggested CARD_ID_START / CARD_ID_END
values for scripts/scrape_sv6a.py. Does not modify any files.

Usage:
    python3 scripts/probe_sv6a_id_range.py
    python3 scripts/probe_sv6a_id_range.py --start 38000 --end 48000
    python3 scripts/probe_sv6a_id_range.py --match "強化拡張パック「ナイトワンダラー」"
"""
import argparse
import re
import sys
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://www.pokemon-card.com/card-search/details.php/card/{}/regu/XY"

# JP set name appears in plaintext on each card detail page in the
# "拡張パック「<set name>」" or "強化拡張パック「<set name>」" attribution line.
DEFAULT_MARKERS = ["ナイトワンダラー"]

# Main set is 64 cards; SAR/UR/AR variants push the total higher (similar to M2a's 193).
# Anything below 64 is definitely not SV6a.
DEFAULT_MIN_DENOMINATOR = 64


def fetch(card_id, timeout=15):
    """Fetch a card detail page; return (status, body) or (None, None) on error."""
    url = BASE_URL.format(card_id)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (SV6a probe)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return None, None


def looks_like_sv6a(html, markers, min_denominator):
    """Return (is_match, card_num, denominator) for a fetched page body."""
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


def coarse_sweep(start, end, step, markers, min_denominator, max_workers=8):
    """Parallel sweep at a coarse step to find any SV6a hit. Returns the first cid that matches."""
    cids = list(range(start, end + 1, step))
    print(f"  coarse sweep: {len(cids)} probes, step={step}, range=[{start}..{end}]")
    hits = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(fetch, cid): cid for cid in cids}
        for f in as_completed(futures):
            cid = futures[f]
            status, body = f.result()
            ok, num, denom = looks_like_sv6a(body, markers, min_denominator)
            mark = "SV6a" if ok else ("?" if body else "·")
            print(f"  probe {cid}: status={status} {mark}")
            if ok:
                hits.append(cid)
    return min(hits) if hits else None


def find_first_contiguous(first_cid, lower_bound, markers, min_denominator, gap, max_probes):
    """From `first_cid`, walk backward until we see `gap` consecutive non-SV6a pages."""
    earliest_match = first_cid
    consecutive_misses = 0
    probes = 0
    for cid in range(first_cid - 1, lower_bound - 1, -1):
        if probes >= max_probes:
            print(f"  → reached --max-probes={max_probes}, stopping backward walk")
            break
        probes += 1
        status, body = fetch(cid)
        is_match, card_num, denom = looks_like_sv6a(body, markers, min_denominator)
        if is_match:
            earliest_match = cid
            consecutive_misses = 0
            print(f"  walk- {cid}: status={status} SV6a (#{card_num}/{denom})")
        else:
            consecutive_misses += 1
            print(f"  walk- {cid}: status={status} miss ({consecutive_misses}/{gap})")
            if consecutive_misses >= gap:
                break
    return earliest_match


def find_last_contiguous(first_cid, end, markers, min_denominator, gap, max_probes):
    """From `first_cid`, walk forward until we see `gap` consecutive non-SV6a pages."""
    last_match = first_cid
    consecutive_misses = 0
    probes = 0
    for cid in range(first_cid + 1, end + 1):
        if probes >= max_probes:
            print(f"  → reached --max-probes={max_probes}, stopping forward walk")
            break
        probes += 1
        status, body = fetch(cid)
        is_match, card_num, denom = looks_like_sv6a(body, markers, min_denominator)
        if is_match:
            last_match = cid
            consecutive_misses = 0
            print(f"  walk+ {cid}: status={status} SV6a (#{card_num}/{denom})")
        else:
            consecutive_misses += 1
            print(f"  walk+ {cid}: status={status} miss ({consecutive_misses}/{gap})")
            if consecutive_misses >= gap:
                break
    return last_match


def main():
    parser = argparse.ArgumentParser(description="Probe pokemon-card.com for SV6a's card-ID range")
    parser.add_argument("--start", type=int, default=38000, help="numeric card ID to start probing (default: 38000)")
    parser.add_argument("--end",   type=int, default=48000,  help="numeric card ID to stop probing at (default: 48000)")
    parser.add_argument("--coarse-step", type=int, default=20, help="step size for coarse sweep (default: 20)")
    parser.add_argument("--match", action="append", default=None, help="set-name marker to look for (repeatable)")
    parser.add_argument("--gap",   type=int, default=8,     help="consecutive non-matching IDs that end the range (default: 8 — SV6a may have non-contiguous secret rares)")
    parser.add_argument("--min-denominator", type=int, default=DEFAULT_MIN_DENOMINATOR, help="minimum NNN/NNN denominator (default: 64)")
    parser.add_argument("--max-probes", type=int, default=300, help="hard cap on walk probes (default: 300)")
    args = parser.parse_args()

    markers = args.match if args.match else DEFAULT_MARKERS
    print(f"Probing for SV6a in [{args.start}..{args.end}], markers={markers}, min_denom={args.min_denominator}, gap={args.gap}")

    print("\nStep 1: coarse parallel sweep")
    first_cid = coarse_sweep(args.start, args.end, args.coarse_step, markers, args.min_denominator)
    if first_cid is None:
        print("\nNo SV6a cards found in the searched range.")
        print("Try widening with --start/--end, or pass --match with a different marker string.")
        sys.exit(1)

    print(f"\nFirst SV6a hit (coarse): numeric ID {first_cid}")

    print("\nStep 2: walk backward to find earliest contiguous card")
    earliest_cid = find_first_contiguous(first_cid, max(1, first_cid - args.coarse_step * 2), markers, args.min_denominator, args.gap, args.max_probes)

    print("\nStep 3: walk forward to find end of contiguous range")
    last_cid = find_last_contiguous(first_cid, args.end + args.coarse_step * 2, markers, args.min_denominator, args.gap, args.max_probes)

    total = last_cid - earliest_cid + 1
    print("\n" + "=" * 60)
    print(f"SV6a first card ID: {earliest_cid}")
    print(f"SV6a last card ID:  {last_cid}")
    print(f"Total IDs in range: {total} (some may be misses for non-SV6a fillers)")
    print("→ Edit scripts/scrape_sv6a.py:")
    print(f"      CARD_ID_START = {earliest_cid}")
    print(f"      CARD_ID_END   = {last_cid}")
    print("=" * 60)


if __name__ == "__main__":
    main()
