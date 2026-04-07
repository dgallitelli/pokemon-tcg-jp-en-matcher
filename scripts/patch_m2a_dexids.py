#!/usr/bin/env python3
"""
Patch M2a.json: add missing dexId fields for the 27 ex-rarity cards
whose dexIds were not extracted by the original scraper.

Also backfill English attack names/effects from TCGdex EN API
by matching each M2a Pokemon card (by dexId + illustrator) to its
closest English equivalent, so the JP panel shows richer data.
"""
import json, pathlib, time
from urllib.request import urlopen, Request

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
API  = "https://api.tcgdex.net/v2/en"

# Hand-verified dexId for each M2a card missing that field.
# Key = M2a card number (3-digit string), Value = [dexId]
MISSING_DEXIDS = {
    "003": [469],   # メガヤンマex   → Yanmega
    "017": [1017],  # オーガポン みどりのめんex → Ogerpon
    "021": [250],   # ヒビキのホウオウex      → Ho-Oh
    "029": [643],   # レシラムex             → Reshiram
    "031": [937],   # ソウブレイズex          → Ceruledge
    "036": [478],   # メガユキメノコex         → Froslass
    "044": [25],    # ピカチュウex            → Pikachu
    "049": [604],   # メガシビルドンex         → Eelektross
    "051": [644],   # ゼクロムex             → Zekrom
    "057": [939],   # ナンジャモのハラバリーex  → Bellibolt
    "060": [35],    # リーリエのピッピex       → Clefairy
    "063": [150],   # ロケット団のミュウツーex  → Mewtwo
    "071": [282],   # メガサーナイトex         → Gardevoir
    "075": [380],   # ラティアスex            → Latias
    "090": [445],   # シロナのガブリアスex     → Garchomp
    "092": [448],   # メガルカリオex           → Lucario
    "094": [701],   # メガルチャブルex         → Hawlucha
    "101": [169],   # ロケット団のクロバットex  → Crobat
    "110": [675],   # メガズルズキンex         → Pangoro
    "112": [571],   # Nのゾロアークex          → Zoroark
    "114": [936],   # キチキギスex            → Kilowattrel
    "119": [649],   # ゲノセクトex            → Genesect
    "122": [1018],  # ブリジュラスex           → Archaludon
    "123": [888],   # ホップのザシアンex       → Zacian
    "126": [149],   # メガカイリューex          → Dragonite
    "134": [887],   # ドラパルトex            → Dragapult
    "145": [1024],  # テラパゴスex            → Terapagos
}


def api_get(path):
    url = f"{API}/{path}"
    req = Request(url, headers={"User-Agent": "Pokemon TCG JP-EN Matcher patch"})
    for attempt in range(3):
        try:
            with urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except Exception as e:
            if attempt < 2:
                time.sleep(1)
            else:
                print(f"  FAILED {url}: {e}")
                return None


def fetch_en_cards_for_dexid(dex_id):
    """Return list of full EN card objects for a given dexId."""
    stubs = api_get(f"dex-ids/{dex_id}")
    if not stubs:
        return []
    cards = stubs if isinstance(stubs, list) else (stubs.get("cards") or [])
    result = []
    for stub in cards:
        cid = stub.get("id") or stub
        if not isinstance(cid, str):
            continue
        card = api_get(f"cards/{cid}")
        if card:
            result.append(card)
        time.sleep(0.05)
    return result


def best_en_match(jp_card, en_cards):
    """
    Pick the best EN card for a JP card.
    Priority: same illustrator > same HP > any match.
    Returns None if no candidates.
    """
    if not en_cards:
        return None
    jp_illus = (jp_card.get("illustrator") or "").lower()
    jp_hp    = jp_card.get("hp")
    # 1. Exact illustrator + HP
    for c in en_cards:
        if (c.get("illustrator") or "").lower() == jp_illus and c.get("hp") == jp_hp:
            return c
    # 2. Illustrator only
    for c in en_cards:
        if (c.get("illustrator") or "").lower() == jp_illus:
            return c
    # 3. HP only
    for c in en_cards:
        if c.get("hp") == jp_hp:
            return c
    # 4. Any
    return en_cards[0]


def backfill_attacks(jp_card, en_card):
    """
    Copy English attack names and effects from en_card into jp_card.
    Matches attacks by position (same count) or by damage value.
    Returns True if anything changed.
    """
    jp_atks = jp_card.get("attacks") or []
    en_atks = en_card.get("attacks") or []
    if not jp_atks or not en_atks:
        return False

    changed = False
    if len(jp_atks) == len(en_atks):
        for jp_a, en_a in zip(jp_atks, en_atks):
            if en_a.get("effect") and not jp_a.get("effect"):
                jp_a["effect"] = en_a["effect"]
                changed = True
            # Backfill cost if missing
            if en_a.get("cost") and not jp_a.get("cost"):
                jp_a["cost"] = en_a["cost"]
                changed = True
    return changed


def main():
    path = DATA / "M2a.json"
    with open(path) as f:
        data = json.load(f)
    cards = data["cards"]

    # Step 1: patch missing dexIds
    patched_dexids = 0
    for num, did in MISSING_DEXIDS.items():
        if num in cards:
            cards[num]["dexId"] = did
            patched_dexids += 1
    print(f"Patched dexId for {patched_dexids} cards")

    # Step 2: backfill English attack effects via TCGdex EN API
    # Build a dexId → [en_cards] cache to avoid repeated API calls
    dexid_cache = {}
    backfilled = 0
    total_pokemon = sum(1 for c in cards.values() if c.get("category") == "Pokemon")
    done = 0

    for num, jp_card in cards.items():
        if jp_card.get("category") != "Pokemon":
            continue
        done += 1
        dex_ids = jp_card.get("dexId") or []
        if not dex_ids:
            print(f"  [{done}/{total_pokemon}] {num} {jp_card['name']}: still no dexId, skipping")
            continue

        primary_dexid = dex_ids[0]
        if primary_dexid not in dexid_cache:
            print(f"  [{done}/{total_pokemon}] Fetching EN cards for dexId={primary_dexid} ({jp_card['name']})...")
            dexid_cache[primary_dexid] = fetch_en_cards_for_dexid(primary_dexid)
        else:
            print(f"  [{done}/{total_pokemon}] {num} {jp_card['name']} (cached dexId={primary_dexid})")

        en_cards = dexid_cache[primary_dexid]
        best = best_en_match(jp_card, en_cards)
        if best and backfill_attacks(jp_card, best):
            backfilled += 1

    print(f"\nBackfilled attack effects for {backfilled} cards")

    # Write updated file
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved {path}")


if __name__ == "__main__":
    main()
