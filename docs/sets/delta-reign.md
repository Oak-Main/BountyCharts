# Delta Reign (ME06) release ledger

Pokémon TCG: Mega Evolution—Delta Reign launches on November 6, 2026. The
[collector page](https://bountycharts.com/sets/delta-reign) gets its editorial
copy and listing data from [the set file](../../data/sets/delta-reign.json).
That file records the source for each listing and the retrieval time for each feed.

## Release facts

| Fact | Evidence |
|---|---|
| November 6 tabletop release | [Pokémon's November product calendar](https://www.pokemon.com/us/news/check-out-every-pokemon-tcg-product-release-in-november-2026) |
| Mega Rayquaza ex returns. Six Stadium cards form three pairs. Each pair makes one panorama. | [Pokémon's expansion announcement](https://press.pokemon.com/en/MEDIA-ALERT-New-Pokemon-Trading-Card-Game-Mega-EvolutionDelta-Reign-Ex) |
| Legendary Pyroduct is numbered 094/103 and 095/103 | [Official card preview](https://www.pokemon.com/us/features/sneak-a-peek-at-cards-from-the-mega-evolution-delta-reign-expansion) and [TCGCSV product catalogue](https://tcgcsv.com/tcgplayer/3/24831/products) |
| Pokémon describes the expansion as over 135 cards. Its October preview also says over 140. | [Product showcase](https://www.pokemon.com/us/news/pokemon-tcg-mega-evolution-delta-reign-product-showcase) and [card preview](https://www.pokemon.com/us/features/sneak-a-peek-at-cards-from-the-mega-evolution-delta-reign-expansion) |

Group 24831 contained 141 consecutively numbered listings at release verification.
The /103 printed on the cards identifies the main set. Numbers 104 through
141 distinguish 38 additional numbered cards. TCGCSV lists 14 illustration
rares, 17 ultra rares and six special illustration rares, consistent with the
publisher's announcement. Listings for sealed products are counted separately.

## Release price snapshot

| Measure | Value |
|---|---|
| TCGCSV source update | 2026-11-05T20:05:46Z |
| Catalogue and prices retrieved and cross-checked | 2026-11-06T06:50:10Z |
| Catalogue and variant quotes | 162 products and 242 price rows |
| Numbered cards with a market price | 134 of 141 |
| Sealed products with a market price | 15 of 21 |
| Missing card market values | Seven, compared with 20 in the November 4 snapshot |

Six of the seven unpriced cards have a low asking price. The other, Talonflame ex
124/103, lacks both values. Mega Rayquaza ex 138/103 has a $397.94 market price.
For 141/103 the feed has a $400.00 low and no market price. The ten highest
quoted singles account for 75% of the sum of one copy of each quoted single.
Ninety of the 134 quoted singles have a market price below $1.

These are release-verification figures. Subsequent snapshots update the
[set file](../../data/sets/delta-reign.json) and the rendered page. The page
shows TCGCSV's [feed update time](https://tcgcsv.com/last-updated.txt) separately
from the time the files were retrieved. All prices are USD.

## Reviewed release-day price refresh (PR #17)

The November 6 release-day refresh advances the provider snapshot to
`2026-11-06T20:05:28Z`, retrieved by the scheduled pipeline at
`2026-11-06T20:11:22Z`. An independent retrieval completed at
`2026-11-07T00:54:02Z` (November 6 Pacific time) rechecked the raw products and
prices with the feed-update receipt read before and after retrieval. Both
receipts still reported that same provider snapshot. The published page at
the start of this review matched main's original release baseline.

All 162 selected market/low pairs and their printing names match the raw
feed after independent conversion to integer cents and application of the
documented selection rule. The catalogue still has 141 numbered cards and
21 sealed SKUs; the feed now has 243 variant price rows, versus 242 at release.
Product IDs, collector numbers, card types and sealed-product classifications
are unchanged. The normalized-row digest is
`e7c65968f7528ad9f368257018988bf88bf115076e1c2e12139501c51ab4ca6b`.

| Coverage | Published release | Reviewed refresh |
|---|---:|---:|
| Cards with a market price | 134 / 141 | 141 / 141 |
| Cards with a low asking price | 140 / 141 | 141 / 141 |
| Sealed SKUs with a market price | 15 / 21 | 15 / 21 |
| Sealed SKUs with a low asking price | 15 / 21 | 15 / 21 |

Every card's market field changes: 133 decrease, one increases, and seven
gain their first reported market price. Of the sealed SKUs, 13 market prices
decrease, one increases and seven are unchanged, including six still missing.
Missing values remain null, not zero, and lows always come from the same
printing as the displayed market price. A low above a market price is retained
when the source reports it; a current asking price and recent sales measure
different things.

| Card | Release market | Refreshed market | Release low | Refreshed low |
|---|---:|---:|---:|---:|
| Mega Rayquaza ex 141/103 | Unavailable | $349.35 | $400.00 | $349.99 |
| Mega Rayquaza ex 138/103 | $397.94 | $327.81 | $448.40 | $339.95 |
| Raikou ex 136/103 | Unavailable | $81.56 | $98.70 | $88.50 |
| Zinnia's Trust 140/103 | $74.94 | $38.42 | $65.69 | $33.00 |
| Mega Golurk ex 137/103 | $49.99 | $32.05 | $37.99 | $29.00 |
| Mega Golisopod ex 135/103 | Unavailable | $21.12 | $37.00 | $20.49 |
| Eevee 114/103 | $37.39 | $20.60 | $29.35 | $19.98 |
| Groudon 111/103 | $36.12 | $15.56 | $28.75 | $13.99 |
| Raikou ex 121/103 | $0.37 | $1.73 | $0.49 | $0.46 |

The other newly priced cards are Wishiwashi ex 120/103 ($5.93 market / $5.14
low), Talonflame ex 124/103 ($12.27 / $10.18), Aarune 125/103 ($3.68 / $3.00)
and Emcee's Hype 128/103 ($3.39 / $2.99). These new observations are coverage
changes, not percentage gains from zero. Talonflame previously lacked both
market and low values.

Two rarity changes were reviewed: Kilowattrel 041/103 (product 728021) and
Darkrai 063/103 (728036) now read Uncommon instead of Common. Both match the
current raw catalogue, and both provider-hosted card images show the Uncommon
diamond beside their collector number. No other rarity changes occur.
Floragato 013/103 switches from Reverse Holofoil to Normal because Normal now
has a market price ($0.11 market / $0.05 low; the reverse row is $0.26 / $0.13).
That follows the existing preference for a priced Normal printing. Talonflame
124/103 gains its first Holofoil row. No other selected printing changes.

The ten highest market quotes total $916.95; all 141 quoted singles total
$1,092.27. Independently calculated, `91695 / 109227 * 100` is
83.9490235931%, correctly rounded to 84%. The original figures were $700.16 /
$933.85 = 74.9756384858%, rounded to 75%. The refreshed verdict correctly leads
with Mega Rayquaza ex 141/103 at $349.35 and counts 100 singles below $1.
The totals describe one copy of each selected printing and include newly
available observations; their difference is not a constant-basket return or
an estimate of pack value. The page distinguishes market from low, labels the
printing, and qualifies these source-reported snapshots as non-guaranteed
transaction prices.

Review validation: the committed-page and sitemap drift checks passed, the
set-page build and site validator passed, all 100 regression tests passed,
and all three documented unit-economics smoke invocations completed. The
refresh workflow remains draft-only, with no merge or production-deploy step.
The original release snapshot above is intentionally retained as history.

## How the prices are selected

Join [products](https://tcgcsv.com/tcgplayer/3/24831/products) and
[prices](https://tcgcsv.com/tcgplayer/3/24831/prices) on product ID. For a
numbered card, choose a printing with a reported market price, preferring
Normal when available. With no market price, use the Normal row if present,
otherwise the first supplied printing. Keep the low and market from that same
row. For a sealed SKU, prefer Normal, matching SetSealed. Both pipelines use
the equivalent of JavaScript's Math.round(value * 100) for positive USD values.

TCGplayer derives [market price](https://help.tcgplayer.com/hc/en-us/articles/213588017-TCGplayer-Market-Price)
from recent completed sales. The low is a listing price. A missing field is
displayed explicitly. Only observed market prices enter the verdict.

## Refresh and publication

Run `python3 scripts/fetch_tcgcsv.py --set delta-reign`, then
`python3 scripts/build_sets.py`, `python3 scripts/validate_site.py` and
`python3 -m unittest discover -s tests`. The release-day refresh is scheduled
for 14:00 UTC on November 6, 2026 (06:00 Pacific). The nightly refresh runs at
21:30 UTC. With no pending draft, ordinary nightly runs skip an unchanged
provider timestamp. The release run, explicit manual runs and updates to an
open draft fetch the files again and record the actual retrieval time.

The job validates the tree and stages changed files on `chore/set-prices`
(or a slug-specific review branch for a scoped dispatch). An open, reserved
draft on the scheduled branch receives the validated commit directly. An
optimistic ref check protects concurrent edits. When starting a new draft,
GitHub Actions attempts to open it. Where repository policy restricts this, the job
verifies the remote head, tree and parent and logs `DRAFT_REQUIRED`. A release
reviewer with PR access can open the draft from those exact SHAs. `DRAFT_OPEN`
means the job verified an existing draft at that head. After a price draft is
merged or closed, use a manual run with a blank set input and open the next
reserved draft from its verified receipt. Ready PRs are excluded from the
refresh. Publishing requires a reviewed merge into main, the Cloudflare
production branch. The deploy workflow then checks the live page, robots and
sitemap against the reviewed result.
