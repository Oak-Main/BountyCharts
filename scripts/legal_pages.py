#!/usr/bin/env python3
"""legal_pages.py - render this site's legal pages from legal/templates and
legal/legal.config.json, and FAIL CLOSED while any {{TOKEN}} in the config is
unresolved, so nothing ships with a placeholder. Added 2026-11-09 (away run);
owner review required before merge.

  python3 scripts/legal_pages.py --check            exit 1 if any token is unresolved
  python3 scripts/legal_pages.py --render [--site site]
        check, then write site/<page>.html for each page in config.pages that does
        not exist yet, and add the inline affiliate notice to pages that carry an
        affiliate link. Commit the result like any other page under site/.
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOKEN = re.compile(r"\{\{([A-Z_]+)\}\}")
TITLES = {"privacy": "Privacy Policy", "terms": "Terms of Use", "affiliate-disclosure": "Affiliate Disclosure"}
AFF = re.compile(r"<a\b[^>]*(rel=\"[^\"]*\bsponsored\b[^\"]*\"|href=\"[^\"]*(amazon\.[a-z.]+/[^\"]*[?&]tag=|/go/)[^\"]*\")", re.I)


def main(argv):
    cfg = json.loads((ROOT / "legal" / "legal.config.json").read_text(encoding="utf-8"))
    unresolved = [f"{k}={v}" for k, v in cfg.items() if isinstance(v, str) and TOKEN.search(v)]
    if unresolved:
        print("legal_pages: FAIL CLOSED - unresolved legal token(s): " + ", ".join(unresolved), file=sys.stderr)
        print("legal_pages: set them in legal/legal.config.json (owner decision) before this site can deploy.", file=sys.stderr)
        return 1
    print("legal_pages: all legal tokens resolved")
    if "--render" not in argv:
        return 0
    site = ROOT / (argv[argv.index("--site") + 1] if "--site" in argv else "site")

    def fill(text):
        def rep(m):
            key = m.group(1).lower()
            if key == "analytics_list":
                return "".join(f"<li>{a}</li>" for a in cfg.get("analytics", [])) or "<li>None</li>"
            if key == "amazon_sentence":
                return "<p>As an Amazon Associate I earn from qualifying purchases.</p>" if cfg.get("amazon") else ""
            if key not in cfg:
                raise SystemExit(f"legal_pages: template token {{{{{m.group(1)}}}}} has no config value")
            return str(cfg[key])
        return TOKEN.sub(rep, text)

    for page in cfg["pages"]:
        dest = site / f"{page}.html"
        if dest.exists() or (site / page / "index.html").exists():
            print(f"legal_pages: {page} already exists; left alone")
            continue
        body = fill((ROOT / "legal" / "templates" / f"{page}.html").read_text(encoding="utf-8"))
        title = TITLES[page]
        dest.write_text(f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} - {cfg['site_name']}</title>
<link rel="canonical" href="{cfg['site_url'].rstrip('/')}/{page}">
<style>
  :root {{
    --bg: #FAFAF8;
    --surface: #FFFFFF;
    --ink: #14181E;
    --ink-soft: #59616E;
    --ink-faint: #6D747F;
    --rule: #E2E4E4;
    --gold: #966C1D;
    --gold-bright: #7A5716;
    --up: #17795E;
    --down: #B23B30;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #0E1116; --surface: #161A21; --ink: #E9ECF1; --ink-soft: #99A2B0;
      --ink-faint: #838C9A; --rule: #232932; --gold: #D9A94F; --gold-bright: #EBC475;
      --up: #4FBF97; --down: #E8756A;
    }}
  }}
  body {{ margin: 0; background: var(--bg); color: var(--ink); }}
  a {{ color: var(--gold); text-underline-offset: 2px; }}
  a:hover {{ color: var(--gold-bright); }}
</style>
</head>
<body>
<main style="max-width:44rem;margin:3rem auto;padding:0 1rem;font-family:system-ui,sans-serif;line-height:1.6">
<p><a href="/">{cfg['site_name']}</a></p>
{body}
</main>
</body>
</html>
""", encoding="utf-8")
        print(f"legal_pages: wrote {dest.relative_to(ROOT)}")

    notice = (f'<p class="affiliate-disclosure-inline" style="font-size:.9em;opacity:.85">This page contains affiliate links. '
              f'{cfg["site_name"]} may earn a commission if you buy through them, at no extra cost to you. '
              f'<a href="{cfg["disclosure_url"]}">Affiliate disclosure</a>.</p>')
    tagged = 0
    for f in site.rglob("*.html"):
        h = f.read_text(encoding="utf-8")
        if not AFF.search(h) or "affiliate-disclosure-inline" in h:
            continue
        m = re.search(r"<main\b[^>]*>", h, re.I) or re.search(r"<body\b[^>]*>", h, re.I)
        if not m:
            continue
        f.write_text(h[: m.end()] + notice + h[m.end():], encoding="utf-8")
        tagged += 1
    print(f"legal_pages: inline affiliate notice added to {tagged} page(s) with affiliate links")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
