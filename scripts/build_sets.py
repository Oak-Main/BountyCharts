#!/usr/bin/env python3
"""
Render the set pages in site/sets/ from the data files in data/sets/.

Run:
    python3 scripts/build_sets.py

Standard library only, matching the rest of the repo.

Three things happen here, and only these three:

  1. Every data/sets/<slug>.json is rendered through templates/set.html into
     site/sets/<slug>.html. A page that still carries an unfilled
     [[COPY: ...]] marker is rendered `noindex,follow`, so placeholder text
     can never reach a search result; it becomes indexable again, with no
     other change, the moment the last marker is replaced.

  2. site/sitemap.xml is rewritten so that a set appears in it only when its
     data file has at least one card row AND its page has no unfilled
     [[COPY: ...]] marker. An empty data file still renders a page (a set that
     exists but has no prices yet), but it is deliberately kept out of the
     sitemap rather than advertised as an indexable page with nothing on it.
     The same applies to a page whose copy has not been written yet.

  3. site/_redirects gets one clean-URL rewrite per set, so /sets/<slug>
     resolves whether or not Cloudflare Pages' automatic HTML handling is on.

The page carries no prices of its own. Prices live in the data file and are
refreshed by scripts/fetch_tcgcsv.py, which reads the same TCGCSV files the
SetSealed daily job reads, so the two sites cannot disagree about a price.
"""

from __future__ import annotations

import argparse
import html
import json
import pathlib
import re
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
DATA = ROOT / "data" / "sets"
SITE = ROOT / "site"
SETS_OUT = SITE / "sets"

SITE_URL = "https://bountycharts.com"

TEMPLATE = TEMPLATES / "set.html"

# Copy that the site's author has not written yet is left in the template as a
# [[COPY: name]] marker (see tests/test_build_sets.py::CopyIsLeftForTheAuthor).
# A page that still contains one must not be indexed or advertised.
COPY_MARKER_RE = re.compile(r"\[\[COPY:[^\]]*\]\]")
ROBOTS_INDEXABLE = "index,follow,max-image-preview:large"
ROBOTS_HELD = "noindex,follow"


def configure(root: pathlib.Path) -> None:
    """Point the builder at a different tree.

    The tests copy the repo into a temporary directory and rebuild there, so
    they never touch the working site/ while proving the sitemap gating.
    """
    global ROOT, TEMPLATES, DATA, SITE, SETS_OUT, TEMPLATE
    ROOT = pathlib.Path(root)
    TEMPLATES = ROOT / "templates"
    DATA = ROOT / "data" / "sets"
    SITE = ROOT / "site"
    SETS_OUT = SITE / "sets"
    TEMPLATE = TEMPLATES / "set.html"


# ---------------------------------------------------------------------------
# A very small template language.
#
#   {{ name }}                 a value, HTML-escaped
#   {{#if name}} ... {{/if}}   a block, taken when the value is truthy
#   {{#unless name}} ... {{/unless}}
#   {{#each list}} ... {{/each}}  repeats the block once per item; inside the
#                              block, names resolve against the item first
#                              and the enclosing scope second
#
# It exists so a page can be written without a build-time dependency, which
# is the same constraint the rest of this repo runs under.
# ---------------------------------------------------------------------------

_VAR_RE = re.compile(r"\{\{\s*([A-Za-z_][\w.]*)\s*\}\}")
_SECTION_RE = re.compile(
    r"\{\{#(if|unless|each)\s+([A-Za-z_][\w.]*)\s*\}\}(.*?)\{\{/\1\}\}",
    re.S,
)


def lookup(scope: list[dict], path: str):
    """Resolve a dotted path against a scope stack (innermost scope first)."""
    for frame in scope:
        if path in frame:
            return frame[path]
    if "." in path:
        head, rest = path.split(".", 1)
        for frame in scope:
            if head in frame and isinstance(frame[head], dict):
                value = lookup([frame[head]], rest)
                if value is not None:
                    return value
    return None


def render(template: str, scope: dict) -> str:
    """Render a template string against a scope mapping."""
    stack: list[dict] = [scope]

    def expand(text: str, current: list[dict]) -> str:
        def replace_section(match: re.Match) -> str:
            kind, name, body = match.group(1), match.group(2), match.group(3)
            value = lookup(current, name)
            if kind == "each":
                if not isinstance(value, (list, tuple)):
                    return ""
                return "".join(expand(body, [dict(item), *current])
                               for item in value)
            truthy = bool(value)
            if kind == "unless":
                truthy = not truthy
            return expand(body, current) if truthy else ""

        def replace_var(match: re.Match) -> str:
            value = lookup(current, match.group(1))
            if value is None:
                return ""
            return html.escape(str(value), quote=True)

        # Sections first, then variables -- but both at THIS scope. Expanding a
        # section body with a different scope and substituting variables
        # afterwards would resolve every {{ name }} against the outermost
        # scope, which silently empties every row of an {{#each}} block.
        text = _SECTION_RE.sub(replace_section, text)
        return _VAR_RE.sub(replace_var, text)

    return expand(template, stack)


# ---------------------------------------------------------------------------
# Data-file -> page scope
# ---------------------------------------------------------------------------

RARITY_ORDER = [
    "Common",
    "Uncommon",
    "Rare",
    "Double Rare",
    "Ultra Rare",
    "Illustration Rare",
    "Special Illustration Rare",
    "Mega Hyper Rare",
]


def cents_to_display(cents) -> str:
    if cents is None:
        return "—"
    return f"${int(cents) / 100:,.2f}"


def rarity_breakdown(cards: list[dict]) -> str:
    counts: dict[str, int] = {}
    for card in cards:
        counts[card.get("rarity") or "Unspecified"] = (
            counts.get(card.get("rarity") or "Unspecified", 0) + 1
        )
    ordered = [r for r in RARITY_ORDER if r in counts]
    ordered += sorted(r for r in counts if r not in RARITY_ORDER)
    if not ordered:
        return ""
    return " · ".join(f"{r} {counts[r]}" for r in ordered)


def price_state(data: dict, cards: list[dict], sealed: list[dict]) -> str:
    """live | from-release-day

    A price row exists for a card only once the market has one. Until then the
    page shows the empty state rather than a zero, which would read as a
    price and not as an absence.
    """
    priced = sum(1 for c in cards if c.get("market_cents") is not None)
    if priced:
        return "live"
    # The release date lives under "set" in the data file. Reading a
    # top-level key that no data file has meant a pre-release set with no
    # card prices was never recognised as pre-release.
    release = (data.get("set") or {}).get("release_date") or data.get("release_date")
    if release and release > datetime.now(timezone.utc).date().isoformat():
        return "from-release-day"
    return "live" if sealed and any(s.get("market_cents") is not None for s in sealed) else "from-release-day"


# The verdict is computed from the same rows the tables show, so it moves
# with every price refresh instead of going stale the day after it is written.
VERDICT_MIN_PRICED = 10


def price_verdict(cards: list[dict]) -> dict:
    """Facts for the "Price verdict" section, or verdict_ready=False when too
    few singles have a market price to say anything honest."""
    priced = sorted(
        (c for c in cards if c.get("market_cents") is not None),
        key=lambda c: (-int(c["market_cents"]), c.get("number") or 0),
    )
    if len(priced) < VERDICT_MIN_PRICED:
        return {"verdict_ready": False}
    total = sum(int(c["market_cents"]) for c in priced)
    top = priced[0]
    top10 = sum(int(c["market_cents"]) for c in priced[:10])
    verdict = {
        "verdict_ready": True,
        "verdict_priced_count": len(priced),
        "verdict_top10_share": round(top10 * 100 / total) if total else 0,
        "verdict_top_name": top.get("name") or "",
        "verdict_top_rarity": top.get("rarity") or "Unspecified",
        "verdict_top_price": cents_to_display(top["market_cents"]),
        "verdict_under_dollar": sum(1 for c in priced if int(c["market_cents"]) < 100),
        "verdict_listing_only": "",
    }
    # A card can have live listings and no market price yet (no sales). When
    # its cheapest listing is above the top market price, leaving it out would
    # misstate where the value is.
    listed = [c for c in cards
              if c.get("market_cents") is None and c.get("low_cents") is not None]
    if listed:
        dearest = max(listed, key=lambda c: int(c["low_cents"]))
        if int(dearest["low_cents"]) > int(top["market_cents"]):
            verdict["verdict_listing_only"] = (
                f" {dearest.get('name')} ({dearest.get('rarity') or 'Unspecified'}) "
                "has no market price yet; its lowest listing is "
                f"{cents_to_display(dearest['low_cents'])}."
            )
    return verdict


def build_scope(data: dict) -> dict:
    cards = list(data.get("cards") or [])
    sealed = list(data.get("sealed") or [])
    retrieved = data.get("retrieved_at_utc") or ""
    set_meta = data.get("set") or {}
    slug = data.get("slug") or ""

    for card in cards:
        card["market_display"] = cents_to_display(card.get("market_cents"))
        card["low_display"] = cents_to_display(card.get("low_cents"))
    for product in sealed:
        product["market_display"] = cents_to_display(product.get("market_cents"))
        product["low_display"] = cents_to_display(product.get("low_cents"))

    state = price_state(data, cards, sealed)
    prices_as_of = data.get("prices_as_of_utc") or retrieved

    scope = {
        "slug": slug,
        "canonical_url": f"{SITE_URL}/sets/{slug}",
        "set": set_meta,
        "set_size": len(cards),
        "set_size_label": data.get("set_size_label") or str(len(cards)),
        "cards_listed": len(cards),
        "cards": cards,
        "sealed": sealed,
        "rarity_breakdown": rarity_breakdown(cards),
        "tcgcsv_group_id": data.get("tcgcsv_group_id"),
        "price_source_label": data.get("price_source", {}).get("name")
        or "TCGplayer market price via TCGCSV",
        "prices_as_of_display": prices_as_of.replace("T", " ").replace("Z", " UTC")
        if prices_as_of else "—",
        "retrieved_at_utc": retrieved,
        "robots_content": ROBOTS_INDEXABLE,
        "prices_pending": state == "from-release-day",
        "prices_pending_note": (
            "Prices from release day. This expansion releases "
            f"{set_meta.get('release_date') or 'soon'}; the "
            "market has no price history for it yet, so the price columns stay "
            "empty until the first close. The columns are wired to the same "
            "TCGCSV feed the rest of this site reads and fill on the first run "
            "after release."
        ),
    }
    scope.update(price_verdict(cards))
    return scope


# ---------------------------------------------------------------------------
# Sitemap
# ---------------------------------------------------------------------------

# The trailing group deliberately does NOT swallow the newline and indent
# that follow the block: a pattern ending in \s* eats the NEXT entry's
# indentation, so removing and re-adding an entry silently changes the
# indentation of the one that follows it.
_URL_BLOCK_RE = re.compile(r"[ \t]*<url>.*?</url>[ \t]*(?:\r?\n)?", re.S)


def _loc_of(block: str) -> str:
    match = re.search(r"<loc>(.*?)</loc>", block, re.S)
    return match.group(1).strip() if match else ""


def write_text(path: pathlib.Path, text: str) -> None:
    """Write UTF-8 with LF endings.

    pathlib.Path.write_text uses the platform newline translation by default,
    so on Windows a "\n" in the source becomes "\r\n" on disk. The files this
    script rewrites are tracked with LF endings and have no .gitattributes
    rule to normalise them, so a Windows build would rewrite every line of
    site/sitemap.xml and show up as a whole-file diff.
    """
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def update_sitemap(managed: dict[str, dict], today: str) -> str:
    """Rewrite site/sitemap.xml.

    `managed` maps slug -> {"url": ..., "lastmod": ..., "empty": bool,
    "unresolved": bool}.
    A set whose data file is empty, or whose page still carries an unfilled
    [[COPY: ...]] marker, is removed from the sitemap; a set with rows and
    finished copy is present exactly once. Every other entry is left
    byte-for-byte alone, so a hand-edited entry survives a rebuild.
    """
    path = SITE / "sitemap.xml"
    text = path.read_text(encoding="utf-8")
    managed_urls = {info["url"]: slug for slug, info in managed.items()}
    kept = []
    for match in _URL_BLOCK_RE.finditer(text):
        block = match.group(0)
        if _loc_of(block) not in managed_urls:
            kept.append(block)

    for slug, info in sorted(managed.items()):
        if info["empty"] or info.get("unresolved"):
            continue
        kept.append(
            "  <url>\n"
            f"    <loc>{info['url']}</loc>\n"
            f"    <lastmod>{info['lastmod']}</lastmod>\n"
            "    <changefreq>daily</changefreq>\n"
            "    <priority>0.7</priority>\n"
            "  </url>\n"
        )

    body = "".join(kept)
    rebuilt = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}"
        "</urlset>\n"
    )
    write_text(path, rebuilt)
    return rebuilt


# ---------------------------------------------------------------------------
# Redirects
#
# There are deliberately no set-page rules here.
#
# An earlier version of this script wrote "/sets/<slug> /sets/<slug>.html 200"
# to site/_redirects, on the assumption that Pages might not resolve the
# extensionless path. It does, and the rule made things worse: Pages
# canonicalises a .html path to its clean form with a 308, so the rewrite sent
# /sets/<slug> to /sets/<slug>.html, which Pages immediately redirected back
# to /sets/<slug>. A 308 loop, verified on the preview deployment for this
# branch. The rule was removed rather than adjusted.
#
# Cloudflare Pages' automatic HTML handling already serves /sets/<slug> from
# site/sets/<slug>.html, exactly as it serves /sealed-vs-singles from
# site/sealed-vs-singles.html.
# ---------------------------------------------------------------------------


def check_redirects_are_clean(slugs: list[str]) -> list[str]:
    """Return any /sets/ rule left in site/_redirects.

    A rule that maps a set path to a .html path re-creates the redirect loop
    described above. The builder does not write these rules; this is a guard
    so that one added by hand is caught before it ships.
    """
    path = SITE / "_redirects"
    if not path.exists():
        return []
    offenders = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("/sets/"):
            continue
        offenders.append(line.strip())
    return offenders


# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the set pages.")
    parser.add_argument("--root", default=None,
                        help="repository root to build (defaults to this repo)")
    args = parser.parse_args(argv)
    if args.root:
        configure(pathlib.Path(args.root))

    if not TEMPLATE.is_file():
        print(f"FAIL  template not found: {TEMPLATE}")
        return 1

    template = TEMPLATE.read_text(encoding="utf-8")
    SETS_OUT.mkdir(parents=True, exist_ok=True)

    managed: dict[str, dict] = {}
    rendered = 0

    for path in sorted(DATA.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        slug = data.get("slug") or path.stem
        scope = build_scope(data)
        out = SETS_OUT / f"{slug}.html"
        page = render(template, scope)
        unresolved = sorted(set(COPY_MARKER_RE.findall(page)))
        if unresolved:
            # Unwritten copy: keep the page reachable but out of search.
            scope["robots_content"] = ROBOTS_HELD
            page = render(template, scope)
        write_text(out, page)
        rendered += 1

        cards = data.get("cards") or []
        lastmod = (data.get("retrieved_at_utc") or "")[:10] or \
            datetime.now(timezone.utc).date().isoformat()
        managed[slug] = {
            "url": f"{SITE_URL}/sets/{slug}",
            "lastmod": lastmod,
            "empty": len(cards) == 0,
            "unresolved": bool(unresolved),
        }
        print(f"ok    {slug}: {len(cards)} card rows, "
              f"{len(data.get('sealed') or [])} sealed rows -> {out.relative_to(ROOT)}")
        if unresolved:
            print(f"hold  {slug}: {len(unresolved)} unfilled copy marker(s) "
                  f"({', '.join(unresolved)}) -> noindex, kept out of the sitemap")

    update_sitemap(managed, datetime.now(timezone.utc).date().isoformat())
    offenders = check_redirects_are_clean(list(managed))
    if offenders:
        for line in offenders:
            print(f"FAIL  site/_redirects: {line} — a rule that maps a set path "
                  f"to a .html path re-creates a 308 redirect loop on Pages")
        return 1
    print(f"ok    sitemap: {len(managed)} set(s) managed")
    print(f"ok    rendered {rendered} set page(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
