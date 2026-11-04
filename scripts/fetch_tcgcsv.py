#!/usr/bin/env python3
"""
Refresh the set data files in data/sets/ from TCGCSV.

Run:
    python3 scripts/fetch_tcgcsv.py            # refresh prices (and any cards
                                              # the feed has added since)
    python3 scripts/fetch_tcgcsv.py --rebuild  # same, but also resets the
                                              # curated metadata back to the
                                              # values in this file

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
import json
import math
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "sets"

TCGCSV_BASE_URL = "https://tcgcsv.com/tcgplayer/3"
TCGCSV_USER_AGENT = "BountyCharts/0.1.0 (+https://bountycharts.com)"
TCGCSV_REQUEST_GAP_MS = 100
TIMEOUT_SECONDS = 30

# Curated metadata that lives in this file rather than in the feed. A rebuild
# restores these; a refresh leaves them alone.
CURATED_KEYS = (
    "set",
    "set_size_label",
    "set_size_source",
    "price_source",
    "sources",
    "official_size_label",
)


# ---------------------------------------------------------------------------
# TCGCSV access
# ---------------------------------------------------------------------------

def fetch_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": TCGCSV_USER_AGENT,
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        if response.status != 200:
            raise RuntimeError(f"{url} -> HTTP {response.status}")
        return json.loads(response.read().decode("utf-8"))


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
    priced = [r for r in rows if r.get("marketPrice") is not None]
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
    if "case" in lowered:
        return "case"
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
            chosen = next((r for r in product_rows
                           if r.get("subTypeName") == "Normal"), None)
            if chosen is None and product_rows:
                chosen = product_rows[0]
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


def refresh_set(path: pathlib.Path, rebuild: bool) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    group_id = data.get("tcgcsv_group_id")
    if not isinstance(group_id, int):
        print(f"FAIL  {path.name}: no integer tcgcsv_group_id")
        return 1

    base = f"{TCGCSV_BASE_URL}/{group_id}"
    try:
        catalogue = fetch_json(f"{base}/products")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            # The set is not in the feed yet. Leave the card list alone and
            # report it; the page falls back to the "prices from release day"
            # state rather than showing an empty price for every card.
            print(f"FAIL  {path.name}: TCGCSV group {group_id} not published yet "
                  f"(HTTP 404) — keeping the existing card list")
            return 2
        print(f"FAIL  {path.name}: {base}/products -> HTTP {exc.code}")
        return 1
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL  {path.name}: {base}/products -> {exc}")
        return 1

    if not catalogue.get("success"):
        print(f"FAIL  {path.name}: TCGCSV reported failure for group {group_id}")
        return 1

    time.sleep(TCGCSV_REQUEST_GAP_MS / 1000)
    try:
        price_payload = fetch_json(f"{base}/prices")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
            json.JSONDecodeError) as exc:
        print(f"FAIL  {path.name}: {base}/prices -> {exc}")
        return 1

    if not price_payload.get("success"):
        print(f"FAIL  {path.name}: TCGCSV reported failure for prices in group {group_id}")
        return 1

    cards, sealed = parse_catalogue(
        catalogue.get("results") or [],
        rows_by_product(price_payload.get("results") or []),
    )

    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    priced = sum(1 for card in cards if card["market_cents"] is not None)

    curated = {key: data[key] for key in CURATED_KEYS if key in data}
    data.update(curated)
    data["cards"] = cards
    data["sealed"] = sealed
    data["retrieved_at_utc"] = retrieved_at
    data["prices_as_of_utc"] = retrieved_at
    data["price_source"] = {
        "name": "TCGplayer market price via TCGCSV",
        "prices_url": f"{base}/prices",
        "catalogue_url": f"{base}/products",
        "group_id": group_id,
        "retrieved_at_utc": retrieved_at,
    }
    if rebuild:
        data["set_size_label"] = data.get("set_size_label") or str(len(cards))

    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"ok    {path.name}: {len(cards)} card rows ({priced} priced), "
          f"{len(sealed)} sealed rows, retrieved {retrieved_at}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild", action="store_true",
                        help="also reset the curated metadata to the values in "
                             "the data file")
    args = parser.parse_args()

    if not DATA.is_dir():
        print(f"FAIL  {DATA} not found")
        return 1

    files = sorted(DATA.glob("*.json"))
    if not files:
        print(f"FAIL  no data files in {DATA}")
        return 1

    failures = 0
    for path in files:
        failures += refresh_set(path, args.rebuild)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
