"""Refresh regression tests. Fixtures represent HTTP responses, not live prices."""

import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import fetch_tcgcsv as fetcher


class RefreshTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = pathlib.Path(tmp.name) / "demo.json"
        self.base = f"{fetcher.TCGCSV_BASE_URL}/99"
        self.products = self.base + "/products"
        self.prices = self.base + "/prices"
        data = {
            "slug": "demo", "tcgcsv_group_id": 99,
            "set": {"release_date": "2001-01-01", "description": "Curated copy"},
            "sources": [{"url": url, "retrieved_at_utc": "original"} for url in
                        (self.products, self.prices, "https://example.org/official")],
            "price_source": {"name": "Curated price label"},
            "cards": [{"market_cents": 120}], "sealed": [],
        }
        self.path.write_text(json.dumps(data))
        product = {"productId": 1, "groupId": 99, "categoryId": 3, "name": "Demo",
                   "extendedData": [{"name": "Number", "value": "001/010"}]}
        self.payloads = {
            fetcher.TCGCSV_UPDATE_URL: "2026-11-05T20:05:46+0000",
            self.products: json.dumps({"success": True, "totalItems": 1, "results": [product]}),
            self.prices: json.dumps({"success": True, "results": [
                {"productId": 1, "subTypeName": "Holofoil", "marketPrice": None, "lowPrice": 0.85}]}),
        }

    def run_refresh(self, fetch=None):
        with patch.object(fetcher, "fetch_text", side_effect=fetch or self.payloads.__getitem__), \
             patch.object(fetcher.time, "sleep"):
            return fetcher.refresh_set(self.path, rebuild=False)

    def test_complete_refresh_sets_provenance_and_preserves_absent_market(self):
        self.assertEqual(self.run_refresh(), 0)
        content = self.path.read_bytes()
        data = json.loads(content)
        self.assertIsNone(data["cards"][0]["market_cents"])
        self.assertEqual(data["cards"][0]["low_cents"], 85)
        self.assertEqual(data["prices_as_of_utc"], "2026-11-05T20:05:46Z")
        self.assertEqual(data["set"]["description"], "Curated copy")
        self.assertEqual(data["price_source"]["name"], "Curated price label")
        self.assertEqual([s["retrieved_at_utc"] for s in data["sources"]],
                         [data["retrieved_at_utc"], data["retrieved_at_utc"], "original"])
        with patch.object(fetcher, "fetch_text", side_effect=self.payloads.__getitem__) as unchanged:
            self.assertEqual(fetcher.refresh_set(self.path, rebuild=False), 0)
            unchanged.assert_called_once_with(fetcher.TCGCSV_UPDATE_URL)
        self.assertEqual(self.path.read_bytes(), content)

    def test_failed_partial_and_mixed_snapshots_preserve_the_file(self):
        original = self.path.read_bytes()
        for url, result in [(self.products, '{"success":true,"results":[]}'),
                            (self.prices, '{"success":true,"results":[]}'),
                            (self.prices, '{"success":false,"results":[]}'),
                            (self.prices, '{"success":true,"results":[{"productId":1,"lowPrice":1},'
                                          '{"productId":999,"marketPrice":10}]}'),
                            (self.products, '{"success":true,"totalItems":2,"results":[]}'),
                            (self.prices, "{bad json")]:
            with self.subTest(url=url, result=result):
                self.assertEqual(self.run_refresh({**self.payloads, url: result}.__getitem__), 1)
                self.assertEqual(self.path.read_bytes(), original)
        times = iter(["2026-11-05T00:00:00Z", "2026-11-06T00:00:00Z"])
        def rolling(url):
            return next(times) if url == fetcher.TCGCSV_UPDATE_URL else self.payloads[url]
        self.assertEqual(self.run_refresh(rolling), 1)
        self.assertEqual(self.path.read_bytes(), original)

    def test_only_an_unpublished_future_group_can_skip_a_404(self):
        def missing(url):
            if url == self.products:
                raise HTTPError(url, 404, "Not found", {}, None)
            return self.payloads[url]
        original = self.path.read_bytes()
        self.assertEqual(self.run_refresh(missing), 1)
        self.assertEqual(self.path.read_bytes(), original)
        data = json.loads(self.path.read_bytes())
        data["set"]["release_date"] = "2999-01-01"
        self.path.write_text(json.dumps(data))
        before = self.path.read_bytes()
        self.assertEqual(self.run_refresh(missing), 0)
        self.assertEqual(self.path.read_bytes(), before)

    def test_manual_slug_limits_the_work(self):
        other = self.path.with_name("other.json")
        other.write_text('{"slug":"other"}')
        with patch.object(fetcher, "DATA", self.path.parent), \
             patch.object(sys, "argv", ["fetch_tcgcsv", "--set", "demo"]), \
             patch.object(fetcher, "refresh_set", return_value=0) as refresh:
            self.assertEqual(fetcher.main(), 0)
            refresh.assert_called_once_with(self.path, False)

    def test_a_case_is_distinct_from_its_contents(self):
        self.assertEqual(fetcher.classify_sealed("Elite Trainer Box Case"), "case")
        self.assertEqual(fetcher.classify_sealed("Elite Trainer Box"), "etb")
