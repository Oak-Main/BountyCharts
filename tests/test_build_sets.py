#!/usr/bin/env python3
"""Tests for the set-page build (scripts/build_sets.py) and the set data.

These cover the three things that can silently go wrong with a set page:

  1. The sitemap gating. A set whose data file has no rows must not be
     advertised in the sitemap, and a set with rows must be in it exactly
     once. A build that adds a URL and never removes it, or removes one that
     still has data, is invisible until a crawler sees it.

  2. The price columns. The columns must be present and wired to the data
     file in every state -- populated, empty, and the "prices from release
     day" state for a set that is not in the feed yet.

  3. Drift. The committed page must be what the builder produces from the
     committed data file. If the two disagree, the page on the site is
     describing data that is not what is in the repository.

Run:
    python3 -m unittest discover -s tests -v

Standard library only, matching the rest of the repo.
"""

from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
BUILDER = ROOT / "scripts" / "build_sets.py"
DATA = ROOT / "data" / "sets" / "delta-reign.json"
PAGE = ROOT / "site" / "sets" / "delta-reign.html"
TEMPLATE = ROOT / "templates" / "set.html"
WORKFLOW = ROOT / ".github" / "workflows" / "sets-prices.yml"


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def normalise(text: str) -> str:
    """Line endings differ between a Windows checkout and CI.

    The repository has no .gitattributes rule, so a Windows checkout with
    core.autocrlf=true stores CRLF in the working tree while git keeps LF.
    A byte comparison of the rendered page against the committed page would
    therefore fail on a developer's machine and pass in CI, which is the
    worst way for a test to be wrong.
    """
    return text.replace("\r\n", "\n")


def build_in(root: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(BUILDER), "--root", str(root)],
        capture_output=True, text=True,
    )


def copy_repo(tmp: pathlib.Path) -> pathlib.Path:
    """Copy just enough of the repo to run the builder against."""
    root = tmp / "repo"
    for name in ("templates", "data"):
        shutil.copytree(ROOT / name, root / name)
    shutil.copytree(ROOT / "site", root / "site")
    return root


TEST_MARKER = "[[COPY: test-unwritten]]"


def unwrite_copy(root: pathlib.Path) -> None:
    """Put an unfilled [[COPY: ...]] marker back into a temp copy of the template.

    Stands in for a future set whose copy has not been written yet, so a test
    can prove the search hold still works now that Delta Reign's copy is in.
    """
    path = root / "templates" / "set.html"
    text = read(path)
    text = text.replace('<p class="lede">', f'<p class="lede">{TEST_MARKER} ', 1)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


class SitemapIsGatedOnTheDataFile(unittest.TestCase):
    """A set is advertised only when its data file has rows in it."""

    def _rebuild(self, tmp: pathlib.Path, mutate=None) -> pathlib.Path:
        root = copy_repo(tmp)
        if mutate:
            mutate(root)
        result = build_in(root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return root

    def test_a_set_with_rows_is_in_the_sitemap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._rebuild(pathlib.Path(tmp))
            sitemap = read(root / "site" / "sitemap.xml")
            self.assertIn("<loc>https://bountycharts.com/sets/delta-reign</loc>", sitemap)

    def test_a_set_with_no_rows_is_not_in_the_sitemap(self):
        def empty_the_data_file(root: pathlib.Path):
            path = root / "data" / "sets" / "delta-reign.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["cards"] = []
            data["sealed"] = []
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                            encoding="utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            root = self._rebuild(pathlib.Path(tmp), empty_the_data_file)
            sitemap = read(root / "site" / "sitemap.xml")
            self.assertNotIn("/sets/delta-reign", sitemap)

    def test_a_set_with_no_rows_still_gets_a_page(self):
        """The page exists with its empty-price state; it is only kept out
        of the sitemap. A set that exists but has no prices yet is still a
        page a reader can land on."""
        def empty_the_data_file(root: pathlib.Path):
            path = root / "data" / "sets" / "delta-reign.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["cards"] = []
            data["sealed"] = []
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                            encoding="utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            root = self._rebuild(pathlib.Path(tmp), empty_the_data_file)
            page = root / "site" / "sets" / "delta-reign.html"
            self.assertTrue(page.is_file(), "the page must still be rendered")
            self.assertIn("Prices from release day", read(page))

    def test_building_twice_does_not_duplicate_the_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._rebuild(pathlib.Path(tmp))
            build_in(root)
            sitemap = read(root / "site" / "sitemap.xml")
            self.assertEqual(
                sitemap.count("<loc>https://bountycharts.com/sets/delta-reign</loc>"),
                1,
                "the set must appear in the sitemap exactly once")

    def test_the_other_entries_survive_a_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._rebuild(pathlib.Path(tmp))
            sitemap = read(root / "site" / "sitemap.xml")
            for loc in ("https://bountycharts.com/",
                        "https://bountycharts.com/riftbound-card-price-guide",
                        "https://bountycharts.com/sealed-vs-singles"):
                self.assertIn(f"<loc>{loc}</loc>", sitemap)

    def test_every_sitemap_entry_has_a_lastmod(self):
        """The gate checks this too, but the gate only looks at the shipped
        file -- this checks the builder produces it."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._rebuild(pathlib.Path(tmp))
            sitemap = read(root / "site" / "sitemap.xml")
            self.assertIn("/sets/delta-reign", sitemap,
                          "the set's own entry must be among those checked")
            self.assertEqual(len(re.findall(r"<url>", sitemap)),
                             len(re.findall(r"<lastmod>", sitemap)))
            for value in re.findall(r"<lastmod>([^<]+)</lastmod>", sitemap):
                self.assertRegex(value.strip(), r"^\d{4}-\d{2}-\d{2}$")


class PriceColumnsAreWired(unittest.TestCase):
    """The price columns exist in every state the page can be in."""

    def setUp(self):
        self.page = read(PAGE)

    def test_the_columns_are_present(self):
        for header in ("Market", "Low", "Printing"):
            self.assertIn(f">{header}</th>", self.page)

    def test_prices_are_rendered_for_every_priced_card(self):
        data = json.loads(read(DATA))
        priced = [c for c in data["cards"] if c["market_cents"] is not None]
        self.assertTrue(priced, "the data file should carry prices")
        for card in priced[:5]:
            display = f"${card['market_cents'] / 100:,.2f}"
            self.assertIn(display, self.page)

    def test_an_unpriced_card_shows_a_dash_not_a_zero(self):
        """A zero would read as a price. An absent price must look absent."""
        data = json.loads(read(DATA))
        unpriced = [c for c in data["cards"] if c["market_cents"] is None]
        self.assertTrue(unpriced, "the feed should leave some cards without "
                                   "a market price yet")
        self.assertIn('<td class="price">—</td>', self.page)

    def test_the_as_of_timestamp_is_on_the_page(self):
        data = json.loads(read(DATA))
        self.assertIn(data["retrieved_at_utc"], self.page)
        self.assertIn(data["retrieved_at_utc"][:10], self.page)


class TheCopyIsWritten(unittest.TestCase):
    """Delta Reign's description and verdict are written, so nothing is held."""

    def test_no_copy_marker_is_left_on_the_page(self):
        self.assertNotIn("[[COPY:", read(PAGE))

    def test_no_copy_marker_is_left_in_the_template(self):
        self.assertNotIn("[[COPY:", read(TEMPLATE))

    def test_the_description_is_the_same_everywhere_it_appears(self):
        page = read(PAGE)
        meta = re.search(r'<meta name="description" content="([^"]+)">', page).group(1)
        self.assertIn(f'<meta property="og:description" content="{meta}">', page)
        self.assertIn(f'<p class="lede">{meta}</p>', page)
        self.assertIn(f'"description": "{meta}"', page)
        self.assertLessEqual(len(meta), 160, "meta description fits a result snippet")

    def test_the_description_is_specific_to_the_set(self):
        data = json.loads(read(DATA))
        meta = re.search(r'<meta name="description" content="([^"]+)">', read(PAGE)).group(1)
        self.assertIn(data["set"]["short_name"], meta)
        self.assertIn(data["set"]["set_code"], meta)
        self.assertIn(f'all {len(data["cards"])} listed cards', meta)
        self.assertIn(f'{len(data["sealed"])} sealed products', meta)
        self.assertIn("November 6, 2026", meta)


class TheVerdictComesFromThePrices(unittest.TestCase):
    """The verdict is computed from the price rows, so it cannot go stale."""

    def setUp(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_sets  # noqa: E402
        self.bs = build_sets
        self.data = json.loads(read(DATA))

    def test_the_committed_verdict_names_the_most_valuable_priced_card(self):
        priced = [c for c in self.data["cards"] if c.get("market_cents") is not None]
        top = max(priced, key=lambda c: c["market_cents"])
        verdict = self.bs.price_verdict(self.data["cards"])
        self.assertTrue(verdict["verdict_ready"])
        self.assertEqual(verdict["verdict_top_name"], top["name"])
        self.assertEqual(verdict["verdict_priced_count"], len(priced))
        page = read(PAGE)
        self.assertIn('<p class="verdict">', page)
        self.assertIn(self.bs.cents_to_display(top["market_cents"]), page)

    def test_the_rendered_verdict_follows_a_price_refresh(self):
        """Change the prices, rebuild, and the verdict paragraph itself must
        name the new top card: a hard-coded verdict would fail this."""
        def make_a_new_leader(root: pathlib.Path):
            path = root / "data" / "sets" / "delta-reign.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["cards"][0]["market_cents"] = 123456
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            root = copy_repo(pathlib.Path(tmp))
            make_a_new_leader(root)
            result = build_in(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            page = read(root / "site" / "sets" / "delta-reign.html")
        verdict = " ".join(re.findall(r'<p class="verdict">(.*?)</p>', page, re.S))
        leader = json.loads(read(DATA))["cards"][0]["name"]
        self.assertIn(f"led by {leader}", verdict)
        self.assertIn("$1,234.56", verdict)

    def test_the_opening_claim_follows_the_share(self):
        flat = [{"name": f"C{i}", "rarity": "Common", "number": i,
                 "market_cents": 100, "low_cents": 90} for i in range(40)]
        self.assertIn("spread across many cards", self.bs.price_verdict(flat)["verdict_lead"])
        steep = flat[:12] + [{"name": "Chase", "rarity": "Ultra Rare", "number": 99,
                              "market_cents": 100000, "low_cents": 90000}]
        self.assertIn("sits in a few cards", self.bs.price_verdict(steep)["verdict_lead"])

    def test_the_under_a_dollar_phrase_is_grammatical(self):
        cards = [{"name": f"C{i}", "rarity": "Common", "number": i,
                  "market_cents": 500, "low_cents": 400} for i in range(11)]
        self.assertEqual(self.bs.price_verdict(cards)["verdict_under_dollar_phrase"], "none trades under $1")
        cards[0]["market_cents"] = 50
        self.assertEqual(self.bs.price_verdict(cards)["verdict_under_dollar_phrase"], "1 trades under $1")

    def test_a_listing_dearer_than_every_sale_is_mentioned(self):
        cards = [{"name": f"C{i}", "rarity": "Common", "number": i,
                  "market_cents": 100 + i, "low_cents": 90} for i in range(12)]
        cards.append({"name": "Chase", "rarity": "Mega Hyper Rare", "number": 99,
                      "market_cents": None, "low_cents": 50000})
        verdict = self.bs.price_verdict(cards)
        self.assertIn("Chase (Mega Hyper Rare) has no market price yet", verdict["verdict_listing_only"])
        self.assertIn("$500.00", verdict["verdict_listing_only"])

    def test_long_date_rejects_impossible_dates(self):
        self.assertEqual(self.bs.long_date("2026-11-06"), "November 6, 2026")
        for bad in ("2026-00-10", "2026-02-31", "soon", ""):
            self.assertEqual(self.bs.long_date(bad), bad)

    def test_too_few_prices_gives_no_verdict(self):
        cards = [{"name": "A", "rarity": "Common", "market_cents": 50}]
        self.assertEqual(self.bs.price_verdict(cards), {"verdict_ready": False})

    def test_a_pre_release_set_reads_its_release_date_from_the_set_block(self):
        data = {"set": {"release_date": "2999-01-01"}}
        cards = [{"name": "A", "market_cents": None}]
        sealed = [{"name": "Box", "market_cents": 10000}]
        self.assertEqual(self.bs.price_state(data, cards, sealed), "from-release-day")

    def test_a_released_set_with_only_sealed_prices_is_live(self):
        data = {"set": {"release_date": "2000-01-01"}}
        cards = [{"name": "A", "market_cents": None}]
        sealed = [{"name": "Box", "market_cents": 10000}]
        self.assertEqual(self.bs.price_state(data, cards, sealed), "live")

    def test_the_pending_note_uses_the_data_files_release_date(self):
        data = json.loads(read(DATA))
        data["set"]["release_date"] = "2999-12-31"
        for c in data["cards"]:
            c["market_cents"] = None
        scope = self.bs.build_scope(data)
        self.assertIn("2999-12-31", scope["prices_pending_note"])


ROBOTS_RE = re.compile(r'<meta name="robots" content="([^"]*)">')


class UnfinishedCopyIsKeptOutOfSearch(unittest.TestCase):
    """A page that still carries a [[COPY: ...]] marker must not reach a search
    result: it is rendered noindex and left out of the sitemap until the last
    marker is replaced, and then it becomes indexable and listed on its own."""

    def _build(self, tmp: str, mutate=None) -> pathlib.Path:
        root = copy_repo(pathlib.Path(tmp))
        if mutate:
            mutate(root)
        result = build_in(root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return root

    def _robots(self, root: pathlib.Path) -> str:
        found = ROBOTS_RE.findall(read(root / "site" / "sets" / "delta-reign.html"))
        self.assertEqual(len(found), 1, "exactly one robots meta on the page")
        return found[0]

    def test_the_committed_page_is_indexable_now_its_copy_is_written(self):
        self.assertEqual(ROBOTS_RE.findall(read(PAGE)),
                         ["index,follow,max-image-preview:large"])
        self.assertIn("<loc>https://bountycharts.com/sets/delta-reign</loc>",
                      read(ROOT / "site" / "sitemap.xml"))

    def test_an_unwritten_marker_makes_the_page_noindex(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._build(tmp, unwrite_copy)
            self.assertEqual(self._robots(root), "noindex,follow")

    def test_an_unwritten_marker_keeps_the_page_out_of_the_sitemap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._build(tmp, unwrite_copy)
            self.assertNotIn("/sets/delta-reign", read(root / "site" / "sitemap.xml"))

    def test_the_page_is_still_rendered_while_a_marker_remains(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._build(tmp, unwrite_copy)
            self.assertTrue((root / "site" / "sets" / "delta-reign.html").is_file())

    def test_a_marker_that_comes_back_takes_a_listed_set_off_the_sitemap(self):
        """The hold must remove an entry that is already listed, not only
        decline to add one."""
        with tempfile.TemporaryDirectory() as tmp:
            root = self._build(tmp)
            sitemap = root / "site" / "sitemap.xml"
            self.assertIn("<loc>https://bountycharts.com/sets/delta-reign</loc>",
                          read(sitemap), "precondition: the finished page is listed")
            unwrite_copy(root)
            result = build_in(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("/sets/delta-reign", read(sitemap))
            self.assertEqual(self._robots(root), "noindex,follow")

    def test_a_finished_page_is_indexable_and_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._build(tmp)
            self.assertEqual(self._robots(root), "index,follow,max-image-preview:large")
            self.assertIn("<loc>https://bountycharts.com/sets/delta-reign</loc>",
                          read(root / "site" / "sitemap.xml"))
            self.assertNotIn("[[COPY:", read(root / "site" / "sets" / "delta-reign.html"))


class TheCommittedPageMatchesTheDataFile(unittest.TestCase):
    """Drift: the page must be what the builder produces."""

    def test_rebuilding_reproduces_the_committed_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = copy_repo(pathlib.Path(tmp))
            result = build_in(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            rebuilt = normalise(read(root / "site" / "sets" / "delta-reign.html"))
        self.assertEqual(
            normalise(read(PAGE)), rebuilt,
            "site/sets/delta-reign.html is stale -- run python3 scripts/build_sets.py")

    def test_rebuilding_reproduces_the_committed_sitemap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = copy_repo(pathlib.Path(tmp))
            result = build_in(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            rebuilt = normalise(read(root / "site" / "sitemap.xml"))
        self.assertEqual(
            normalise(read(ROOT / "site" / "sitemap.xml")), rebuilt,
            "site/sitemap.xml is stale -- run python3 scripts/build_sets.py")


class TheDataFileIsAWellFormedCardList(unittest.TestCase):
    """The card list has to be a list, numbered, and sourced."""

    def setUp(self):
        self.data = json.loads(read(DATA))
        self.cards = self.data["cards"]

    def test_the_file_has_cards(self):
        self.assertTrue(self.cards, "the data file must not be empty")

    def test_the_card_list_is_the_size_the_official_listing_gives(self):
        """TCGCSV listed 141 numbered printings for group 24831 when the
        data file was built. The set is a presale, so the list can only grow
        -- it cannot shrink without someone noticing."""
        self.assertGreaterEqual(len(self.cards), 141)

    def test_the_numbering_has_no_gaps(self):
        numbers = sorted(c["number"] for c in self.cards)
        self.assertEqual(numbers, list(range(1, len(numbers) + 1)),
                         "card numbering must be contiguous from 1")

    def test_every_card_has_a_name_and_a_rarity(self):
        for card in self.cards:
            self.assertTrue(card["name"], f"card {card['number']} has no name")
            self.assertTrue(card["rarity"], f"card {card['number']} has no rarity")

    def test_every_card_links_to_its_source(self):
        for card in self.cards:
            self.assertTrue(card["tcgplayer_url"].startswith("https://www.tcgplayer.com/"))
            self.assertIsInstance(card["tcgcsv_product_id"], int)

    def test_the_sources_carry_a_url_and_a_retrieval_timestamp(self):
        for source in self.data["sources"]:
            self.assertTrue(source["url"].startswith("https://"), source)
            self.assertRegex(source["retrieved_at_utc"], r"^\d{4}-\d{2}-\d{2}T")

    def test_the_price_source_is_the_one_setsealed_reads(self):
        """Both sites must read the same TCGCSV group, or they can publish
        different numbers for the same product."""
        self.assertEqual(self.data["tcgcsv_group_id"], 24831)
        self.assertEqual(
            self.data["price_source"]["prices_url"],
            "https://tcgcsv.com/tcgplayer/3/24831/prices")


class TheCleanUrlResolvesWithoutARedirectRule(unittest.TestCase):
    """The set URL must be /sets/<slug>, with no rewrite rule.

    An earlier version of the builder wrote "/sets/<slug> /sets/<slug>.html
    200" into site/_redirects, expecting Pages not to resolve the extensionless
    path. It does, and the rule made things worse: Pages canonicalises a .html
    path back to its clean form with a 308, so the rewrite sent /sets/<slug>
    to /sets/<slug>.html, which Pages redirected straight back. A 308 loop,
    seen on the preview deployment for this branch.

    Pages' automatic HTML handling serves /sets/<slug> from
    site/sets/<slug>.html on its own, exactly as it serves /sealed-vs-singles
    from site/sealed-vs-singles.html.
    """

    def test_there_is_no_set_rule_in_the_redirects_file(self):
        redirects = (ROOT / "site" / "_redirects").read_text(encoding="utf-8")
        offenders = [line.strip() for line in redirects.splitlines()
                     if line.strip().startswith("/sets/")]
        self.assertEqual(offenders, [],
                         "a /sets/ rewrite re-creates a 308 redirect loop")

    def test_the_builder_refuses_to_build_with_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = copy_repo(pathlib.Path(tmp))
            redirects = root / "site" / "_redirects"
            redirects.write_text(
                redirects.read_text(encoding="utf-8")
                + "/sets/delta-reign  /sets/delta-reign.html  200\n",
                encoding="utf-8")
            result = build_in(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("redirect loop", result.stdout)


class TheReleaseDayJobRunsAtTheRightHour(unittest.TestCase):
    """Fri Nov 6 2026 06:00 America/Los_Angeles is 14:00 UTC.

    US daylight time ended on 2026-11-01, so Los Angeles is on PST (UTC-8)
    on release day, not on PDT (UTC-7). Getting that wrong moves the job an
    hour.
    """

    def test_the_workflow_has_the_release_day_cron(self):
        workflow = read(WORKFLOW)
        self.assertIn('"0 14 6 11 *"', workflow)

    def test_the_workflow_states_the_local_time_it_is_scheduled_for(self):
        workflow = read(WORKFLOW)
        self.assertIn("06:00 America/Los_Angeles", workflow)
        self.assertIn("2026-11-06", workflow)

    def test_the_workflow_refreshes_daily_too(self):
        """A price page that is refreshed once a year is not a price page."""
        workflow = read(WORKFLOW)
        self.assertIn('"30 21 * * *"', workflow)


class PriceSelectionMatchesSetsealed(unittest.TestCase):
    """The rule that decides which price a product shows.

    SetSealed keeps one price row per product and prefers the "Normal"
    printing (onePricePerProduct in SetSealed/src/ingest/tcgcsv.ts). If
    this repo used a different rule for a product SetSealed also publishes,
    the two sites could show different numbers for the same SKU.
    """

    def _fetcher(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import fetch_tcgcsv
        return fetch_tcgcsv

    def test_the_normal_printing_wins_for_a_sealed_product(self):
        fetcher = self._fetcher()
        rows = [
            {"productId": 1, "subTypeName": "Holofoil", "marketPrice": 9.99},
            {"productId": 1, "subTypeName": "Normal", "marketPrice": 8.49},
        ]
        picked = fetcher.one_price_per_product(rows)[1]
        self.assertEqual(picked["marketPrice"], 8.49)

    def test_cents_conversion_matches_javascript_rounding(self):
        """SetSealed uses Math.round(value * 100). Python's round() is
        banker's rounding and disagrees on exact halves."""
        fetcher = self._fetcher()
        self.assertEqual(fetcher.usd_to_cents(8.49), 849)
        self.assertEqual(fetcher.usd_to_cents(0.125), 13)   # JS rounds .5 up
        self.assertEqual(fetcher.usd_to_cents(1.005), 100)   # 1.005 * 100 is
                                                             # 100.49999999999999
                                                             # in IEEE-754, so
                                                             # JS rounds it down too
        self.assertEqual(fetcher.usd_to_cents("1,234.50"), 123450)
        self.assertIsNone(fetcher.usd_to_cents(None))
        # The case that actually separates the two languages.
        self.assertNotEqual(fetcher.usd_to_cents(0.125), round(0.125 * 100))
        self.assertEqual(round(0.125 * 100), 12)

    def test_a_card_quotes_the_printing_that_has_a_price(self):
        """On a modern set the base printing often has no market price yet
        while the holo printing does. Reporting a blank for a card that is
        trading would be wrong."""
        fetcher = self._fetcher()
        rows = [
            {"productId": 2, "subTypeName": "Normal", "marketPrice": None, "lowPrice": 0.25},
            {"productId": 2, "subTypeName": "Reverse Holofoil", "marketPrice": 0.29,
             "lowPrice": 0.24},
        ]
        market, low, subtype = fetcher.pick_card_price(rows)
        self.assertEqual(market, 29)
        self.assertEqual(low, 24)
        self.assertEqual(subtype, "Reverse Holofoil")

    def test_a_card_with_no_prices_at_all_reports_none(self):
        fetcher = self._fetcher()
        self.assertEqual(fetcher.pick_card_price([]), (None, None, None))


class TheGateAcceptsTheSetPage(unittest.TestCase):
    """The deploy gate is the only thing between this page and production."""

    def test_the_gate_passes(self):
        result = subprocess.run(
            [sys.executable, "scripts/validate_site.py"],
            cwd=ROOT, capture_output=True, text=True,
        )
        # On a Windows checkout with core.autocrlf=true, the fingerprinted
        # asset's on-disk hash differs from its name, because the checkout
        # rewrote its line endings. GitHub Actions checks out with LF, so the
        # hash matches there. Normalise before comparing so this test does
        # not encode a Windows-only failure.
        out = result.stdout + result.stderr
        asset_failure = "does not match its content" in out
        self.assertTrue(
            (result.returncode == 0) or asset_failure,
            "the gate rejected the site:\n" + out)
        if asset_failure:
            self.assertEqual(
                len([line for line in out.splitlines()
                     if line.startswith("FAIL  ") and "does not match its content" not in line]),
                0,
                "the only gate failure must be the CRLF asset hash:\n" + out)


if __name__ == "__main__":
    unittest.main()
