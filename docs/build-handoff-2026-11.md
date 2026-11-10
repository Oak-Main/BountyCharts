# BountyCharts build handoff — November 2026

**Scope of this document:** the build-out from its beginning state to where it
stands today, and the goals the whole build serves. It is written for whoever
picks the build up next — a human owner or an agent — and it is meant to be
read before touching anything.

**Written:** 2026-11-06 (Pacific). **Base commit:** `3bc5fd4` (main).
**Site:** <https://bountycharts.com> · **Repo:** `Oak-Main/BountyCharts`

---

## 1. Where the build stood on November 6

The site went from **a research publication with a static marketing page** to
**a working price-data platform that publishes a live set page and refreshes
itself daily**, without a merge-to-main deploy step being automated in a way
that can publish unreviewed data.

The concrete state:

| | |
|---|---|
| Set pages live | 1 — `/sets/delta-reign` (Pokémon TCG: Mega Evolution—Delta Reign, ME06) |
| Published URLs | 10 in the sitemap (9 content pages + the set page) |
| Card rows published | 141 numbered printings, with rarity, type, HP, printing, market and low prices |
| Price source | TCGplayer via TCGCSV, set group `24831` — the same file SetSealed's nightly ingest reads |
| Refresh | Nightly at 21:30 UTC; release-day job at 14:00 UTC on 2026-11-06 |
| Publication rule | **Draft-only.** A refresh opens or updates a draft PR; a reviewed merge into `main` is what publishes |
| Tests | 100, green on a Linux/LF checkout |
| Last verified retrieval | `2026-11-06T20:11:22Z` (provider snapshot `2026-11-06T20:05:28Z`) |
| Open PRs at this snapshot | #19, draft, `chore/set-prices`, holding the next refresh |


**November 9 reconciliation.** The November 6 table is historical. The refresh from [PR #19](https://github.com/Oak-Main/BountyCharts/pull/19) has merged. `main` at `aa39a34c` records a provider retrieval of `2026-11-09T01:09:52Z`. The public set page and sitemap both returned HTTP 200 during the November 9 review.

---

## 2. Beginning state (2026-11-04)

At base commit `eb8810b` the repository was **research, not product**. The
complete file tree was:

```
.github/workflows/deploy.yml      docs/  (9 files)          models/unit_economics.py
.gitignore                         .wrangler/cache/         prompts/agency-handoff-prompt.md
_headers                           site/  (9 pages)         README.md
                                  scripts/  (2 files)       tests/  (2 files)
```

Concretely, what existed and what did not:

**Existed**
- Nine hand-written HTML content pages plus a 404, a `robots.txt`, a
  `sitemap.xml`, `_headers`, `_redirects` and four fingerprinted assets.
- `scripts/validate_site.py` — a real deploy gate: tag balance, required meta,
  dark-theme CSS, sitemap validity, fingerprinted-asset hashes, and a
  CSP-subresource check.
- `scripts/fingerprint_assets.py` — content-hashes `site/assets/` and rewrites
  references, because `/assets/*` is cached `immutable` for a year.
- `tests/test_assets.py`, `tests/test_validate_site.py` — behavioural tests for
  the gate itself.
- `.github/workflows/deploy.yml` — validate → deploy to Cloudflare Pages.
- `docs/` — the deep dive, the fact-check ledger, the scorecard, the owner
  action list, the content and image spec, the visual elevation brief.
- A live site at `bountycharts.com` serving those 9 pages.

**Did not exist**
- No data files. No templates. No build step. No price pipeline.
- No set pages, and no sitemap generation.
- No scheduled jobs of any kind.
- No second set, no card-level data, no per-card prices.

**The gap this build closed:** bountycharts.com was a property with a strategy
and no product. The sister site **SetSealed** (`Oak-Main/SetSealed`) already
had the machinery a set page needs — `site/templates/product.html`,
`data/seed/products.csv`, the `src/ingest/tcgcsv.ts` adapter, a Worker cron
(`30 21 * * *`), D1/KV/R2 — and already tracked Delta Reign's sealed SKUs
(`me06-*` rows). But SetSealed sells **sealed product**; the card-level list
nobody owned.

**The strategic finding that shaped the work** is in the repo's own
`docs/tcg-deep-dive-2026.md`, written before any of this: *"The report is a
good market description and a poor business plan."* Four structural flaws
were corrected — the closed TCGplayer API, the Pokémon Pocket monetization
paradox, the false "tooling moat", and an inverted price ladder. Pokémon
scored **highest audience, lowest legal safety**, because TPCi's licence is
explicitly non-commercial. That single fact governs everything below.

---

## 3. Build goals overall

These are the repo's own goals, not new ones. The set-page build is one
concrete slice of them.

### 3.1 The corrected roadmap (`docs/tcg-deep-dive-2026.md` §5)

| Phase | Window | Goal |
|---|---|---|
| **1** | Months 0–6 | **One game, one wedge.** Lead with **Riftbound** — permissive IP policy, real secondary market, active meta, still-thin information layer. Budget a price-data vendor from day one. |
| **2** | Months 3–9 | **Monetize in the correct order: affiliate first, ads second, subscriptions third.** The original ordering was backwards for a zero-traffic property. |
| **3** | Months 9–18 | **Subscriptions, repriced.** Reframe away from falsifiable return promises ("buy at $5 before it hits $30") toward decision support — price history, spread analysis, reprint risk, movement alerts. Removes the FTC exposure and the self-defeating scaling. |
| **4** | Month 12+ | **Expand in risk order: One Piece → Star Wars: Unlimited → MTG. Add Pokémon last, physical only, behind legal review.** Pokémon TCG Pocket can be free ad-only top-of-funnel, but must never sit behind the same paywall as everything else. |

### 3.2 Constraints that must survive every future change

1. **Pokémon is free, ad-only, never paywalled.** TPCi's licence is
   non-commercial. The repo's own build spec (`prompts/agency-handoff-prompt.md`)
   makes this mechanically enforced: every row with `game == 'pokemon'` must
   resolve to tier `free`, and a test fails the build otherwise. **The
   Delta Reign page has no monetization surface at all** — no affiliate, no
   subscription, no paid placement.
2. **No buy signals, no price predictions.** The site's stated position is
   decision support: what the data says and where it came from. Broadcasting
   a buy signal creates the spike and turns later readers into exit liquidity.
3. **Every changed data value carries its source URL and a UTC retrieval
   timestamp**, in the data file, on the page, and in the PR body.
4. **The credibility asset is the fact-check ledger** (38 claims, audited one
   at a time). A price page that cannot be traced to a source is the failure
   mode the whole repo is built against.
5. **A price is a snapshot, not a truth.** Market prices are TCGplayer's
   derivation from recent completed sales; low is a listing price. Missing
   values are displayed as absent, never as zero.

### 3.3 Where this build sits in that plan

The set page is the **first production slice of the price-data platform** the
roadmap assumes — but it is deliberately the *free* slice. It proves the
chassis: a source-grounded card list with prices, published automatically,
refreshable, and impossible to publish unreviewed. Riftbound (Phase 1's wedge,
and the game with the permissive IP and the real affiliate surface) will use
the same chassis with a different price vendor and a different monetization
surface. Everything built here is reusable for every set that follows.

---

## 4. What was built, end to end

### 4.1 The pipeline

```
TCGCSV (TCGplayer mirror)
  https://tcgcsv.com/tcgplayer/3/24831/products    <- card list, numbering, rarity
  https://tcgcsv.com/tcgplayer/3/24831/prices       <- market + low, per printing
        |
        |  scripts/fetch_tcgcsv.py     join on product id; pick the printing;
        |                            convert to integer cents; stamp the
        |                            retrieval time and the provider snapshot
        v
  data/sets/delta-reign.json          <- the single source of truth for the page
        |
        |  scripts/build_sets.py       render templates/set.html; rewrite
        |                            site/sitemap.xml; refuse /sets/ redirects
        v
  site/sets/delta-reign.html          <- the published page
        |
        |  scripts/validate_site.py   the deploy gate (all of site/, nested
        |                            pages included)
        |  scripts/verify_live_set.py compare the published page, robots and
        |                            sitemap on the real hostname
        v
  reviewed merge into main  ->  Cloudflare Pages (Git integration) -> production
```

### 4.2 File map

| File | Role |
|---|---|
| `data/sets/delta-reign.json` | The data file. 141 card rows + 21 sealed rows, with rarity, type, HP, printing, market/low in integer cents, the TCGCSV product id and URL per card, the retrieval time, the provider snapshot time, and a SHA-256 of the rows used. |
| `templates/set.html` | The set template. One template for every set. Contains the price columns, the empty-price state, and the data-driven verdict. |
| `scripts/fetch_tcgcsv.py` | The price hook. `--set <slug>` scopes a run; a bare run does every set. |
| `scripts/build_sets.py` | The builder. Renders every `data/sets/*.json`, rewrites the sitemap, and fails if a `/sets/` rule has appeared in `_redirects`. |
| `scripts/verify_live_set.py` | Verifies a published set against the custom domain — page, robots, sitemap. |
| `scripts/validate_site.py` | The pre-existing deploy gate, now covering nested pages. |
| `scripts/fingerprint_assets.py` | The pre-existing asset fingerprinter. |
| `tests/test_build_sets.py` | Sitemap gating, price-column states, copy markers, drift, the redirect guard, the release-day cron, and the SetSealed price-selection rules. |
| `tests/test_fetch_tcgcsv.py`, `tests/test_verify_live_set.py` | The fetch and live-verification behaviours. |
| `tests/test_assets.py`, `tests/test_validate_site.py` | The pre-existing gate tests. |
| `.github/workflows/sets-prices.yml` | The refresh job: release-day + nightly, draft-only publication. |
| `.github/workflows/deploy.yml` | The pre-existing validate → deploy workflow, extended with the set build step and the new path filters. |
| `docs/sets/delta-reign.md` | The per-set source ledger: every value, its source URL, its retrieval time, the set-size analysis, and the refresh/publication mechanics. |
| `.gitattributes` | `site/assets/** -text` — fingerprinted filenames refer to exact bytes, so they must not be newline-translated. |

### 4.3 The agreement contract with SetSealed

The two sites must never publish different numbers for the same product. That
is enforced by sharing three things, not by convention:

1. **The same file.** `https://tcgcsv.com/tcgplayer/3/24831/prices`. SetSealed
   maps `ME06` to groups `24831` and `2374`; this repo uses `24831`.
2. **The same row.** For sealed SKUs, one price row per product, preferring the
   `Normal` printing — identical to SetSealed's `onePricePerProduct`.
3. **The same rounding.** `floor(value * 100 + 0.5)`, which is what JS
   `Math.round(value * 100)` does. Python's `round()` is banker's rounding and
   disagrees on exact halves, so `round()` is deliberately not used.

Cards deliberately use a *different* rule, because a card is one product with a
price row per printing (`Normal`, `Reverse Holofoil`, `Holofoil`, …): the page
quotes the printing that has a market price, prefers `Normal` when several do,
and **names the printing in its own column**. On a modern set the base
printing frequently has no market price yet while the holo printing does, and
reporting a blank for a card that is trading would be wrong.

### 4.4 Sitemap gating

A set is advertised in `site/sitemap.xml` **only when its data file has card
rows in it**. A set with no rows still renders a page — with the "prices from
release day" state — but is kept out of the sitemap, so a page with nothing on
it is never advertised as indexable. The builder rewrites only the entries it
manages; every other sitemap entry is left byte-for-byte alone.

---

## 5. How it got here

| PR | Commit | What it did |
|---|---|---|
| **#14** | `80db35f` | The build-out: data file, template, price hook, builder, sitemap gating, release-day + nightly cron, deploy wiring, 29 tests, the set ledger. |
| **#15** | `0e01cf0` | Resolved the `[[COPY:]]` markers into data-driven fields (`seo_description`, `robots_content`) and a computed verdict; release-day fixes. |
| — | `27c68b4` | A price refresh commit on the refresh branch. |
| **#16** | `e88440d` | Published the verified Delta Reign set guide; guarded draft price refreshes. |
| **#17** | `a627e38` | **Published the verified release-day pricing refresh** — the post-release data and the corrected verdict. |
| **#18** | `3d0345a` | Verified refreshed draft commits after GitHub propagation. |
| **#19** | *(open draft)* | Reserves the `chore/set-prices` review branch for subsequent scheduled refreshes. |
| **#20** | `3bc5fd4` | Pinned `actions/checkout` v7.0.1 and `peter-evans/create-pull-request` v8.1.1 to upstream release SHAs (Node 24), and completed the price-refresh handoff in `docs/sets/delta-reign.md`. |

---

## 6. Live state, verified 2026-11-06

Measured against the production hostname, not the checkout:

```
GET https://bountycharts.com/sets/delta-reign   -> 200, 85,942 bytes
  card rows                                    141
  retrieved / provider snapshot                 2026-11-06T20:11:22Z / 2026-11-06T20:05:28Z
  rarity split   Common 50 · Uncommon 33 · Rare 10 · Double Rare 10 ·
                 Ultra Rare 17 · Illustration Rare 14 · Special Illustration Rare 6 ·
                 Mega Hyper Rare 1
  verdict       The ten highest market prices account for 84% of the total for one
                copy of each priced single, led by Mega Rayquaza ex 141/103
                (Mega Hyper Rare) at $349.35. Of the 141 quoted singles, 100 trade
                under $1.
GET https://bountycharts.com/sitemap.xml        -> 200, 10 urls, includes /sets/delta-reign
```

**The set is out.** The presale caveat expired: TCGplayer now lists all 141
printings with a market price, and two rarities moved at release — Kilowattrel
041/103 and Darkrai 063/103 are now **Uncommon**, not Common. Both were
confirmed against the raw catalogue and against the provider's own card images.
The page reflects the current feed.

---

## 7. How to operate it

### Commands

```bash
python3 scripts/fetch_tcgcsv.py --set delta-reign   # refresh one set's prices
python3 scripts/fetch_tcgcsv.py                     # refresh every set
python3 scripts/build_sets.py                       # render pages + rewrite the sitemap
python3 scripts/validate_site.py                   # the deploy gate
python3 -m unittest discover -s tests               # 100 tests
python3 scripts/verify_live_set.py                  # verify production
```

### Schedules

| Job | Cron (UTC) | Local | When |
|---|---|---|---|
| Release-day refresh | `0 14 6 11 *` | 06:00 America/Los_Angeles, Fri 2026-11-06 | Once, on release day. **PST, not PDT** — US daylight time ended 2026-11-01. |
| Nightly refresh | `30 21 * * *` | 13:30 Pacific | Every day, in the same slot SetSealed's TCGCSV ingest runs (`30 21 * * *`), so both sites read the same refreshed file inside the same window. |

### The publication rule

**The refresh job never merges and never deploys.** It validates the tree and
stages the changed files on `chore/set-prices` (or a slug-specific review
branch for a scoped dispatch). Publishing requires a **reviewed merge into
`main`**, the Cloudflare production branch. The deploy workflow then checks the
live page, robots and sitemap against the reviewed result.

### Adding the next set

1. Create `data/sets/<slug>.json` with the curated metadata: set name, set
   code, release date, `tcgcsv_group_id`, the official size label, and the
   `sources` list with retrieval timestamps.
2. `python3 scripts/fetch_tcgcsv.py --set <slug>` — populates the card list,
   the sealed rows and the prices.
3. `python3 scripts/build_sets.py` — renders `site/sets/<slug>.html` and adds
   the sitemap entry (because the data file now has rows).
4. Open a PR. The builder discovers data files automatically; nothing else is
   set-specific.

---

## 8. Open items

| # | Item | Whose call |
|---|---|---|
| 1 | **PR #19** — the reserved draft holding the next price refresh. It needs a reviewer with PR access, and it should be kept open until a substantive snapshot has been reviewed for publication. | Owner |
| 2 | **"Allow GitHub Actions to create and approve pull requests" is disabled at repository level.** The refresh job detects this and logs `DRAFT_REQUIRED` instead of failing; a reviewer then opens the draft from the exact SHAs the run verified. No repository or organization permissions were changed, and none should be without the owner's decision. | Owner |
| 3 | **Next set.** The chassis is set-agnostic — a Riftbound set page is the natural next one, because Phase 1 names Riftbound as the wedge and it is the game with the permissive IP and the real affiliate surface. | Owner |
| 4 | **Price data vendor.** The deep dive says budget a third-party vendor from day one. TCGCSV is free and Patreon-supported, derived from TCGplayer's API terms, and credited as *"TCGplayer market price via TCGCSV"* on every published price. Whether that is sustainable is an open procurement question, not a technical one. | Owner |
| 5 | **Open research questions** carried in the deep dive §7: Riftbound's 45% LGS margin (unsourced and load-bearing), Riot's tooling roadmap (closes the wedge if it ships pricing), and vendor licence/redistribution terms. | Owner |

---

## 9. Invariants and gotchas

Things that will bite the next person. Each one cost real time.

1. **Never add a `_redirects` rule that maps a clean path to its `.html`
   file.** Cloudflare Pages canonicalises a `.html` path back to the clean form
   with a **308**, so the rule sends the request to a path that redirects
   straight back — a **308 loop** with `Location` equal to the request URL.
   Pages' automatic HTML handling already resolves extensionless paths, nested
   ones included. The builder now refuses to run if a `/sets/` rule exists.
2. **A Windows `core.autocrlf=true` checkout breaks the asset-fingerprint
   check.** The checkout rewrites LF→CRLF, so the on-disk hash of
   `ga4.d611d877.js` becomes `a74ef35f` and 7 tests fail. Hash the
   LF-normalised bytes before believing a fingerprint failure, and always
   establish the baseline on a pristine `origin/main` worktree before blaming
   your change.
3. **Write generated files with explicit LF.**
   `pathlib.Path.write_text` applies platform newline translation and turns
   every `\n` into `\r\n` on Windows — a one-line change becomes a whole-file
   diff. Use `open(path, "w", encoding="utf-8", newline="\n")`.
4. **The sitemap is rebuilt, not appended to.** Entries the builder manages are
   replaced; every other entry is preserved. A block-matching regex that
   swallows trailing whitespace will quietly re-indent the entry that follows —
   keep the match tight.
5. **Variable substitution must happen at the scope that owns it.** Expanding
   an `{{#each}}` body and substituting variables afterwards resolves every
   `{{ name }}` against the outermost scope and silently empties every row.
6. **A missing price is not a zero.** Unpriced cards render an em dash and are
   excluded from the verdict's totals. A zero would read as a price.
7. **The verdict is computed from the priced rows only**, and it says so —
   "for one copy of each priced single" — because the totals describe a
   basket of observed snapshots, not a constant-basket return and not an
   estimate of pack value.

---

## 10. Where to read more

| Document | What it answers |
|---|---|
| [`docs/sets/delta-reign.md`](sets/delta-reign.md) | The per-set source ledger: every value, its source, its retrieval time, the set-size analysis, the price-selection rules, and the refresh/publication mechanics. |
| [`docs/tcg-deep-dive-2026.md`](tcg-deep-dive-2026.md) | Why the build exists: the four structural flaws in the source report, the corrected roadmap, and the open questions. |
| [`docs/fact-check-ledger.md`](fact-check-ledger.md) | 38 claims, audited one at a time: 17 confirmed, 5 overstated, 10 materially wrong, 6 unsourced. The credibility asset. |
| [`docs/deployment/cloudflare.md`](deployment/cloudflare.md) | The Pages runbook. |
| [`prompts/agency-handoff-prompt.md`](../prompts/agency-handoff-prompt.md) | The full build spec for the platform: the PriceVendor interface, the entitlement matrix, the `game` vocabulary, and the Pokémon-free rule with its mechanical enforcement. |
| [`models/unit_economics.py`](../models/unit_economics.py) | The funnel model behind every revenue figure in the deep dive. |
