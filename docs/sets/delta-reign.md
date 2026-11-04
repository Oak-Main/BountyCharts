# Delta Reign (ME06) — source ledger

The set page at `/sets/delta-reign` is built from `data/sets/delta-reign.json`.
This file records where every value in that data file came from, and which
facts are still provisional.

Set: **Pokémon TCG: Mega Evolution—Delta Reign** (set code `ME06`)
Release: **November 6, 2026**

## Sources

| What | Source | Retrieved (UTC) |
|---|---|---|
| Card list, numbering, rarity, type, HP | TCGplayer catalogue via TCGCSV, group `24831` — <https://tcgcsv.com/tcgplayer/3/24831/products> | 2026-11-04T17:54:00Z |
| Market and low prices | TCGplayer market price via TCGCSV, group `24831` — <https://tcgcsv.com/tcgplayer/3/24831/prices> | 2026-11-04T17:54:00Z |
| Release date, official card count | The Pokémon Company International, *Pokémon TCG: Mega Evolution—Delta Reign product showcase* — <https://www.pokemon.com/us/news/pokemon-tcg-mega-evolution-delta-reign-product-showcase> | 2026-11-04T16:45:00Z |
| Expansion page | Pokémon TCG official expansion page — <https://tcg.pokemon.com/en-us/expansions/delta-reign/> | 2026-11-04T16:45:00Z |

## Set size: 103 or 135 or 141?

Three numbers are in play and they are not the same quantity.

- **"over 135 cards"** — the official figure. The Pokémon Company International
  states the expansion "boasts more than 135 cards" and lists "Number of Cards:
  Over 135" in the product showcase. The final English count has not been
  published.
- **141 numbered printings** — what TCGCSV lists for group `24831` at the
  retrieval time. Numbering runs 1–141 with no gaps.
- **103** — the denominator TCGplayer prints on every card in the set
  (`001/103`, `138/103`, `141/103`). It is the main-set base number, not the
  count of numbered printings.

The same pattern appears on a set that has already released: *Destined Rivals*
(group `24269`) lists 244 numbered printings against a `/182` base. So the
denominator is the base set and the extra numbers are additional printings.

**What the page says:** "Official size: over 135 cards" and "Cards listed:
141". Both are sourced, and the gap between them is TPCi not having published
a final count.

## Rarity counts cross-check

TCGCSV's rarity split for the 141 listed printings:

| Rarity | Count |
|---|---|
| Common | 52 |
| Uncommon | 31 |
| Rare | 10 |
| Double Rare | 10 |
| Ultra Rare | 17 |
| Illustration Rare | 14 |
| Special Illustration Rare | 6 |
| Mega Hyper Rare | 1 |

TPCi's announcement states the rare slots as "six Special Illustration Rares,
14 Illustration Rares and 17 Ultra Rares". TCGCSV agrees on all three, and
6 + 14 + 17 = 37, consistent with TPCi's "more than 35 cards that use special
illustration treatments".

## Prices

Prices come from the same TCGCSV group file SetSealed's nightly ingest reads,
so the two sites cannot disagree about a product they both publish.

The rule that decides which price row a product shows differs by product type,
deliberately:

- **Sealed product** — one row per product, preferring the `Normal` printing.
  Identical to SetSealed's `onePricePerProduct`. A sealed SKU has one
  printing, so the choice is unambiguous and both sites land on the same
  number.
- **Card** — one product, one price row per printing (`Normal`,
  `Reverse Holofoil`, `Holofoil`, …). The page quotes the printing that has a
  market price, preferring `Normal` when several do, and says which printing
  it is quoting in the *Printing* column. On a modern set the base printing
  frequently has no market price yet while the holo printing does; reporting
  a blank for a card that is trading would be wrong.

Prices are converted to integer cents with `floor(value * 100 + 0.5)`, which
is what JavaScript's `Math.round(value * 100)` does. Python's `round()` is
banker's rounding and disagrees on exact halves, so `round()` is not used.

## Still provisional

- TCGplayer marks every product in this set as a presale: *"card details,
  including rarity and card name, may change up until release date."* The card
  list, the rarity split and the set size can all change before November 6.
- 20 of the 141 printings have no market price yet — almost all of them the
  higher-numbered art variants. Those rows show a dash for market and, where
  TCGCSV has one, a low price.
- The official English card count has not been published.

## Where the page lives

- Page: <https://bountycharts.com/sets/delta-reign>
- Data: `data/sets/delta-reign.json`
- Template: `templates/set.html`
- Build: `python3 scripts/build_sets.py`
- Refresh: `python3 scripts/fetch_tcgcsv.py`
