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
