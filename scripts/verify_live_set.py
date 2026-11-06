"""Verify a published set on the custom domain against this checkout."""

import json
import pathlib
import sys
import time
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from http.client import HTTPException

SITE = pathlib.Path(__file__).resolve().parents[1] / "site"
ORIGIN = "https://bountycharts.com"


class SetPage(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.meta = {}
        self.text = []
        self.section = ""
        self.feed(markup)
        self.close()

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if tag in ("title", "main"):
            self.section = tag
        elif tag == "script" and attr.get("type") == "application/ld+json":
            self.section = "json"
        elif tag == "meta":
            key = attr.get("name") or attr.get("property") or ""
            if key in ("robots", "description", "bc:data-retrieved") or key.startswith("og:"):
                self.meta[key] = attr.get("content")
        elif tag == "link" and attr.get("rel") == "canonical":
            self.meta["canonical"] = attr.get("href")
        elif tag == "a" and self.section == "main":
            self.text.append(attr.get("href", ""))

    def handle_endtag(self, tag):
        if tag == self.section or (tag == "script" and self.section == "json"):
            self.section = ""

    def handle_data(self, data):
        if self.section == "json":
            self.meta["structured"] = json.loads(data)
        elif self.section in ("title", "main"):
            self.text.extend(data.split())


def get(url):
    request = urllib.request.Request(url, headers={"User-Agent": "BountyCharts/1.0 release check",
                                                  "Cache-Control": "no-cache"})
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status != 200 or response.geturl() != url:
            raise ValueError(f"{url} resolved to {response.status} {response.geturl()}")
        directives = ",".join(response.headers.get_all("X-Robots-Tag", [])).lower()
        return response.read().decode("utf-8"), directives


def verify(slug):
    url = f"{ORIGIN}/sets/{slug}"
    expected = SetPage((SITE / "sets" / f"{slug}.html").read_text(encoding="utf-8"))
    markup, directives = get(url)
    live = SetPage(markup)
    if live.meta != expected.meta or live.text != expected.text or live.meta["canonical"] != url:
        raise ValueError("live content or metadata differs from the reviewed page")
    indexable = "index" in live.meta["robots"].split(",")
    if indexable and ("noindex" in directives or "none" in directives):
        raise ValueError(f"unexpected X-Robots-Tag: {directives}")
    sitemap, _ = get(f"{ORIGIN}/sitemap.xml")
    entries = [e for e in ET.fromstring(sitemap).findall("{*}url") if e.findtext("{*}loc") == url]
    if len(entries) != int(indexable):
        raise ValueError("wrong canonical occurrence count in live sitemap")
    rules, _ = get(f"{ORIGIN}/robots.txt")
    robots = urllib.robotparser.RobotFileParser()
    robots.parse(rules.splitlines())
    if indexable and (not robots.can_fetch("Googlebot", url)
                      or f"{ORIGIN}/sitemap.xml" not in (robots.site_maps() or [])):
        raise ValueError("robots.txt blocks crawling or omits the sitemap")
    print(f"HTTP 200 {url}, sitemap.xml and robots.txt; canonical={url}; "
          f"robots={live.meta['robots']}; sitemap entries={len(entries)}; "
          f"reviewed content, prices and metadata match; retrieved={live.meta['bc:data-retrieved']}")


if __name__ == "__main__":
    for attempt in range(12):
        try:
            verify(sys.argv[1])
            break
        except (OSError, HTTPException, ValueError, ET.ParseError) as error:
            if attempt == 11:
                sys.exit(str(error))
            print(f"Waiting for the Git deployment: {error}", flush=True)
            time.sleep(10)
