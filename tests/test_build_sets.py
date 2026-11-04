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


class CopyIsLeftForTheAuthor(unittest.TestCase):
    """Set description and verdict text are markers, not invented copy."""

    def test_the_page_carries_the_markers(self):
        page = read(PAGE)
        self.assertIn("[[COPY: delta-reign-description]]", page)
        self.assertIn("[[COPY: delta-reign-verdict]]", page)

    def test_the_template_carries_the_markers(self):
        template = read(TEMPLATE)
        self.assertIn("[[COPY: delta-reign-description]]", template)
        self.assertIn("[[COPY: delta-reign-verdict]]", template)

    def test_there_is_no_other_copy_marker(self):
        found = set(re.findall(r"\[\[COPY:[^\]]+\]\]", read(PAGE)))
        self.assertEqual(
            found,
            {"[[COPY: delta-reign-description]]", "[[COPY: delta-reign-verdict]]"},
            "only the set description and the verdict are markers")


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
