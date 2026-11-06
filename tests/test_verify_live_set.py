import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import verify_live_set as live


class ProductionGate(unittest.TestCase):
    def setUp(self):
        self.slug = "delta-reign"
        self.url = f"{live.ORIGIN}/sets/{self.slug}"
        self.files = {url: ((live.SITE / path).read_text(encoding="utf-8"), "") for url, path in (
            (self.url, "sets/delta-reign.html"),
            (f"{live.ORIGIN}/robots.txt", "robots.txt"),
            (f"{live.ORIGIN}/sitemap.xml", "sitemap.xml"),
        )}

    def test_live_content_matches_reviewed_files(self):
        with patch.object(live, "get", side_effect=self.files.__getitem__):
            live.verify(self.slug)

    def test_rejects_stale_copy_header_block_and_stale_sitemap(self):
        for path, updated in [
                (self.url, (self.files[self.url][0].replace('class="lede">', 'class="lede">Stale '), "")),
                (self.url, (self.files[self.url][0], "googlebot: noindex")),
                (f"{live.ORIGIN}/sitemap.xml", ("<urlset/>", "")),
                (f"{live.ORIGIN}/robots.txt", ("User-agent: *\nDisallow: /\n", ""))]:
            with self.subTest(path=path), patch.object(live, "get", side_effect={**self.files, path: updated}.__getitem__):
                with self.assertRaises(ValueError):
                    live.verify(self.slug)
