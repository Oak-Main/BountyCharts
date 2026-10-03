# HANDOFF — BountyCharts (bountycharts.com)

Remediation Wave 1. Branch `mm/fixwave1`, branched off a freshly fetched `main`
(`faa8541 seo: robots meta on all static pages (PR #11)`).

**No site file was changed. Nothing to fix.** This repo is the live sitemap
reconciliation, and the reconciliation came back clean.

## A correction to the earlier finding

The previous wave report said `site/` held 2 built pages while `sitemap.xml`
declared 9, and concluded the repo was incomplete. **That was wrong, and the
cause was a stale local snapshot.** `C:\Users\Dell\BountyCharts` was an old
checkout; a fresh clone of `kevynsgrin-a11y/BountyCharts` at `main` contains all
9 pages plus `404.html`, matching its sitemap exactly.

Recording the correction because the earlier claim was made confidently and
would have sent someone to rebuild a repo that was already correct.

## Generated, not hand-maintained

`site/` is the deployable static site and its HTML is committed. There is no
generator and no build command — `package.json` has no `scripts` block at all.
Per the wave's own rule, "if there is no build command, stop on this repo", no
source edit was possible or attempted.

## B9 — the sitemap reconciliation, run as specified

`site/sitemap.xml` declares 9 URLs. Every one was fetched live at **1 request per
second**, with a 20s timeout, following redirects.

| # | URL | Live status |
| --- | --- | --- |
| 1 | `https://bountycharts.com/` | 200 |
| 2 | `/how-to-price-a-card-collection` | 200 |
| 3 | `/riftbound-card-price-guide` | 200 |
| 4 | `/card-grading-guide` | 200 |
| 5 | `/selling-fees-comparison` | 200 |
| 6 | `/what-is-the-metagame` | 200 |
| 7 | `/chase-cards-explained` | 200 |
| 8 | `/card-condition-guide` | 200 |
| 9 | `/sealed-vs-singles` | 200 |

**9 of 9 live. 0 returning 404.**

Per the rule — "if every URL returns 200 live, make no change and record that in
HANDOFF.md" — **no sitemap entry was removed, because none needed to be.** The
live site and the repo agree on every URL, so there is no "live site and repo
disagree" stop condition either.

Full evidence, including the status of each URL and the timestamp:
`census-sitemap-reconciliation.json`, committed alongside this handoff.

## What the audit had flagged here, for context

From the earlier 3-domain sample, against a stale 2-page snapshot:

| Finding | Status now |
| --- | --- |
| 1 missing meta description, on `404.html` | Still real, not fixed |
| 1 meta description over 155 chars, on `404.html` | Still real, not fixed |
| 1 missing canonical, on `404.html` | Still real, not fixed |
| 1 thin-page noindex candidate, `404.html` | Weak candidate — it is a 404, and noindexing a 404 adds nothing |
| 1 × P4 `link-unverified` — `undercovertourist.com` returns 403 | Not a defect; third-party bot policy |
| 0 × P1, 0 × P2 | — |

All three outstanding items are in the head of a single file, `site/404.html`.
Adding a canonical or a meta description to a 404 page is arguably the wrong
call in the first place, so this is left as a decision rather than a mechanical
fix.

## Files changed

- `census-sitemap-reconciliation.json` — the evidence, added so the "no change"
  conclusion is auditable rather than just asserted.
- `HANDOFF.md` — this file.

No `dist/`, no build, no deploy.
