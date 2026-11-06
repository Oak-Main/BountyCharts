#!/usr/bin/env python3
"""
Refresh the set data files in data/sets/ from TCGCSV.

Run:
    python3 scripts/fetch_tcgcsv.py            # refresh prices (and any cards
                                              # the feed has added since)
    python3 scripts/fetch_tcgcsv.py --set delta-reign
    python3 scripts/fetch_tcgcsv.py --rebuild  # renew the retrieval receipt
                                              # even for an unchanged snapshot

Standard library only, matching the rest of the repo.

WHY THIS FILE EXISTS IN THIS FORM
---------------------------------
SetSealed (the sister site) runs a nightly ingest against TCGCSV. This
script reads the *same* files, with the *same* row-selection rule, so the two
sites cannot publish different numbers for the same product. Concretely:

  * Same URL.      TCGCSV mirrors TCGplayer's catalogue as one JSON file per
                   set ("group"): https://tcgcsv.com/tcgplayer/3/{group}/prices
                   and .../products. SetSealed fetches group 24831 for ME06
                   (see TCGCSV_GROUPS_BY_SET_CODE in the SetSealed repo); this
                   script fetches the same group for the same set.

  * Same row.      A product can carry several price rows, one per printing.
                   SetSealed keeps one row per product and prefers the
                   "Normal" printing (onePricePerProduct in
                   SetSealed/src/ingest/tcgcsv.ts). This script keeps the
                   same one, so a product resolves to one price on both sites.

  * Same rounding. SetSealed converts USD to integer cents with
                   Math.round(value * 100) (parseUsdToCents in
                   SetSealed/src/ingest/normalize.ts). JS Math.round rounds
                   halves away from zero, which Python's round() does NOT do
                   (banker's rounding), so the conversion is done explicitly
                   here rather than with round().

  * Same etiquette. TCGCSV asks for an "App/X.Y.Z" User-Agent -- a generic or
                   missing one gets HTTP 401 -- and for ~100 ms between
                   requests so the caller is not throttled.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.client import HTTPException

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "sets"

TCGCSV_BASE_URL = "https://tcgcsv.com/tcgplayer/3"
TCGCSV_UPDATE_URL = "https://tcgcsv.com/last-updated.txt"
TCGCSV_USER_AGENT = "BountyCharts/0.1.0 (+https://bountycharts.com)"
TCGCSV_REQUEST_GAP_MS = 100
TIMEOUT_SECONDS = 30

# ---------------------------------------------------------------------------
# TCGCSV access
# ---------------------------------------------------------------------------

def fetch_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": TCGCSV_USER_AGENT,
            "Accept": "application/json, text/plain",
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        if response.status != 200:
            raise RuntimeError(f"{url} -> HTTP {response.status}")
        return response.read().decode("utf-8")


def feed_time() -> str:
    stamp = datetime.fromisoformat(fetch_text(TCGCSV_UPDATE_URL).strip())
    if stamp.tzinfo is None:
        raise ValueError("TCGCSV update timestamp has no time zone")
    return stamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_rows(url: str) -> list[dict]:
    payload = json.loads(fetch_text(url))
    rows = payload.get("results") if isinstance(payload, dict) else None
    if (not isinstance(rows, list) or payload.get("success") is not True
            or payload.get("errors") or payload.get("totalItems", len(rows)) != len(rows)
            or any(not isinstance(row, dict) or type(row.get("productId")) is not int for row in rows)):
        raise ValueError(f"invalid or incomplete TCGCSV response for {url}")
    return rows


def usd_to_cents(value) -> int | None:
    """USD -> integer cents, matching SetSealed's Math.round(value * 100)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if not math.isfinite(value) or value < 0:
            return None
        return math.floor(value * 100 + 0.5)
    if not isinstance(value, str):
        return None
    cleaned = value.replace("$", "").replace(",", "").replace(" ", "").strip()
    if cleaned == "":
        return None
    try:
        number = float(cleaned)
    except ValueError:
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return math.floor(number * 100 + 0.5)


def one_price_per_product(rows: list[dict]) -> dict[int, dict]:
    """Keep one price row per product, preferring the "Normal" printing.

    Mirrors onePricePerProduct in SetSealed/src/ingest/tcgcsv.ts so a product
    resolves to the same price on both sites.
    """
    by_product: dict[int, dict] = {}
    for row in rows:
        product_id = row.get("productId")
        if not isinstance(product_id, int):
            continue
        kept = by_product.get(product_id)
        if kept is None or (kept.get("subTypeName") != "Normal"
                            and row.get("subTypeName") == "Normal"):
            by_product[product_id] = row
    return by_product


def rows_by_product(rows: list[dict]) -> dict[int, list[dict]]:
    """All price rows for a product, keyed by product id."""
    by_product: dict[int, list[dict]] = {}
    for row in rows:
        product_id = row.get("productId")
        if not isinstance(product_id, int):
            continue
        by_product.setdefault(product_id, []).append(row)
    return by_product


def pick_card_price(rows: list[dict]) -> tuple[int | None, int | None, str | None]:
    """Pick the printing a card's market and low prices come from.

    A single card is one TCGplayer product with one price row per printing
    ("Normal", "Reverse Holofoil", "Holofoil", ...). SetSealed's rule --
    prefer "Normal" -- is the right rule for SEALED products, where a product
    has exactly one printing and both sites must land on the same number. It
    is the wrong rule for a card: on a modern set the base "Normal" printing
    frequently has no market price yet while the holo printing does, and
    reporting a blank for a card that is trading would be wrong.

    So for cards: take the printing that actually has a market price,
    preferring "Normal" when several do; if no printing has one, fall back to
    "Normal" for the low price.
    """
    if not rows:
        return None, None, None
    normal = next((r for r in rows if r.get("subTypeName") == "Normal"), None)
    priced = [r for r in rows if usd_to_cents(r.get("marketPrice")) is not None]
    if priced:
        chosen = next((r for r in priced if r.get("subTypeName") == "Normal"), priced[0])
    else:
        chosen = normal or rows[0]
    return (
        usd_to_cents(chosen.get("marketPrice")),
        usd_to_cents(chosen.get("lowPrice")),
        chosen.get("subTypeName"),
    )


# ---------------------------------------------------------------------------
# Parsing the catalogue
# ---------------------------------------------------------------------------

def extended(product: dict, field: str) -> str | None:
    for entry in product.get("extendedData") or []:
        if entry.get("name") == field:
            value = entry.get("value")
            return value if isinstance(value, str) else None
    return None


def classify_sealed(name: str) -> str:
    lowered = name.lower()
    if re.search(r"\bcase\b", lowered):
        return "case"
    if "elite trainer box" in lowered:
        return "etb" if "pokemon center" not in lowered else "pc_etb"
    if "booster box" in lowered:
        return "booster_box"
    if "booster bundle" in lowered:
        return "bundle"
    if "booster pack" in lowered:
        return "booster_pack"
    if "build & battle" in lowered or "build and battle" in lowered:
        return "collection"
    if "blister" in lowered:
        return "blister"
    if "checklane" in lowered:
        return "checklane"
    return "sealed_product"


def parse_catalogue(products: list[dict], prices: dict[int, list[dict]]) -> tuple[list[dict], list[dict]]:
    """Split the catalogue into numbered cards and sealed product SKUs.

    Cards and sealed products use different price-selection rules on purpose.
    A sealed SKU is one product with one printing, so it takes SetSealed's
    rule (one row per product, preferring "Normal") and the two sites land on
    the same number. A card is one product with a row per printing, so it
    takes pick_card_price and the page says which printing it is quoting.
    """
    cards: list[dict] = []
    sealed: list[dict] = []

    for product in products:
        product_id = product.get("productId")
        number_field = extended(product, "Number")
        product_rows = prices.get(product_id, []) if isinstance(product_id, int) else []

        if number_field:
            market_cents, low_cents, subtype = pick_card_price(product_rows)
            raw_number, _, raw_denominator = number_field.partition("/")
            try:
                number = int(raw_number)
            except ValueError:
                number = None
            try:
                denominator = int(raw_denominator)
            except ValueError:
                denominator = None
            name = product.get("name") or ""
            # TCGplayer appends the number to the card name for some printings;
            # strip it so the name is the card name, not the label.
            clean = re.sub(r"\s+-\s+\d+/\d+$", "", name).strip()
            cards.append({
                "number": number,
                "name": clean,
                "rarity": extended(product, "Rarity") or "",
                "card_type": extended(product, "Card Type") or "",
                "hp": extended(product, "HP") or "",
                "stage": extended(product, "Stage") or "",
                "print_number": number_field,
                "print_denominator": denominator,
                "tcgcsv_product_id": product_id,
                "tcgplayer_url": product.get("url") or "",
                "market_cents": market_cents,
                "low_cents": low_cents,
                "price_subtype": subtype,
            })
        else:
            name = product.get("name") or ""
            chosen = one_price_per_product(product_rows).get(product_id)
            sealed.append({
                "name": name,
                "product_type": classify_sealed(name),
                "tcgcsv_product_id": product_id,
                "tcgplayer_url": product.get("url") or "",
                "market_cents": usd_to_cents(chosen.get("marketPrice")) if chosen else None,
                "low_cents": usd_to_cents(chosen.get("lowPrice")) if chosen else None,
                "price_subtype": chosen.get("subTypeName") if chosen else None,
            })

    cards.sort(key=lambda c: (c["number"] is None, c["number"] or 0))
    sealed.sort(key=lambda p: p["name"])
    return cards, sealed


# ---------------------------------------------------------------------------


def rows_digest(cards: list, sealed: list) -> str:
    """Fingerprint the complete normalized catalogue used for a fast-path check."""
    encoded = json.dumps([cards, sealed], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def refresh_set(path: pathlib.Path, rebuild: bool) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    group_id = data.get("tcgcsv_group_id")
    if not isinstance(group_id, int):
        print(f"FAIL  {path.name}: no integer tcgcsv_group_id")
        return 1

    base = f"{TCGCSV_BASE_URL}/{group_id}"
    catalogue_url, prices_url = f"{base}/products", f"{base}/prices"
    try:
        as_of = feed_time()
        if (not rebuild and data.get("prices_as_of_utc") == as_of and data.get("cards")
                and isinstance(data.get("sealed"), list)
                and data.get("price_source", {}).get("rows_sha256") == rows_digest(data["cards"], data["sealed"])):
            print(f"ok    {path.name}: already holds TCGCSV snapshot {as_of}")
            return 0
        time.sleep(TCGCSV_REQUEST_GAP_MS / 1000)
        products = fetch_rows(catalogue_url)
        time.sleep(TCGCSV_REQUEST_GAP_MS / 1000)
        quotes = fetch_rows(prices_url)
        time.sleep(TCGCSV_REQUEST_GAP_MS / 1000)
        if feed_time() != as_of:
            raise ValueError("TCGCSV updated during retrieval; retry the refresh")
        if any(p.get("groupId") != group_id or p.get("categoryId") != 3 for p in products):
            raise ValueError("catalogue contains a product outside the requested group")
        known_ids = {p["productId"] for p in products}
        if len(known_ids) != len(products):
            raise ValueError("duplicate product IDs in catalogue")
        if any(row["productId"] not in known_ids for row in quotes):
            raise ValueError("prices include a product outside the fetched catalogue")
        cards, sealed = parse_catalogue(products, rows_by_product(quotes))
        if not cards:
            raise ValueError("catalogue has no numbered cards")
        had_quotes = any(row.get(k) is not None for row in [*data.get("cards", []), *data.get("sealed", [])]
                         for k in ("market_cents", "low_cents"))
        if had_quotes and not any(row[k] is not None for row in [*cards, *sealed]
                                  for k in ("market_cents", "low_cents")):
            raise ValueError("no usable prices for a previously quoted set")
    except urllib.error.HTTPError as exc:
        release = (data.get("set") or {}).get("release_date") or ""
        if (exc.code == 404 and exc.url in (catalogue_url, prices_url)
                and release > datetime.now(timezone.utc).date().isoformat()):
            print(f"skip  {path.name}: group {group_id} pending before release")
            return 0
        print(f"FAIL  {path.name}: {exc.url} -> HTTP {exc.code}; snapshot preserved")
        return 1
    except (OSError, HTTPException, ValueError, RuntimeError) as exc:
        print(f"FAIL  {path.name}: {exc}; snapshot preserved")
        return 1

    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    priced = sum(card["market_cents"] is not None for card in cards)
    data.update(cards=cards, sealed=sealed, retrieved_at_utc=retrieved_at, prices_as_of_utc=as_of)
    source = data.setdefault("price_source", {})
    source.setdefault("name", "TCGplayer market price via TCGCSV")
    source.update(prices_url=prices_url, catalogue_url=catalogue_url, group_id=group_id,
                  retrieved_at_utc=retrieved_at, rows_sha256=rows_digest(cards, sealed))
    for entry in data.get("sources", []):
        if entry.get("url") in (catalogue_url, prices_url):
            entry["retrieved_at_utc"] = retrieved_at

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent,
                                     delete=False) as handle:
        temporary = pathlib.Path(handle.name)
        try:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    print(f"ok    {path.name}: {len(cards)} card rows ({priced} priced), "
          f"{len(sealed)} sealed rows, retrieved {retrieved_at}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild", action="store_true",
                        help="renew the retrieval receipt even for an unchanged feed")
    parser.add_argument("--set", default="", metavar="SLUG", help="refresh only this set slug")
    args = parser.parse_args()

    if not DATA.is_dir():
        print(f"FAIL  {DATA} not found")
        return 1

    files = sorted(DATA.glob("*.json"))
    if args.set:
        files = [path for path in files
                 if (json.loads(path.read_text(encoding="utf-8")).get("slug") or path.stem) == args.set]
    if not files:
        print(f"FAIL  no matching set {args.set!r} in {DATA}")
        return 1

    failures = 0
    for path in files:
        failures += refresh_set(path, args.rebuild)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
