"""One-off probe: robots.txt rules and page structure for candidate report sources.

Prints status, robots.txt verdicts and structural hints (link patterns, table/AJAX markers) so a
scraper can be designed without guessing. Fetches a handful of pages, 3 s apart.

    uv run python scripts/probe_sources.py
"""

from __future__ import annotations

import re
import time
import urllib.robotparser
from collections import Counter
from urllib.parse import urljoin, urlparse

import requests

USER_AGENT = "uap-geo-research/0.1 (+https://github.com/Fagundo/uap-geo)"
DELAY_S = 3.0

SITES = {
    "nuforc": [
        "https://nuforc.org/databank/",
        "https://nuforc.org/ndx/?id=event",
        "https://nuforc.org/subndx/?id=e202401",
        "https://nuforc.org/sighting/?id=180000",
    ],
    "mufon": [
        "https://mufon.com/",
        "https://mufoncms.com/",
    ],
    "enigma": [
        "https://www.enigmalabs.io/",
        "https://www.enigmalabs.io/terms",
    ],
}

PATTERNS = {
    "subndx links": r"subndx/\?id=[^\"'&<> ]+",
    "ndx links": r"/ndx/\?id=[^\"'&<> ]+",
    "sighting links": r"sighting/\?id=\d+",
    "admin-ajax": r"admin-ajax\.php[^\"'<> ]*",
    "wpDataTables": r"wdt[A-Za-z_]*|wpdatatable[^\"'<> ]*",
    "api urls": r"https?://[^\"'<> ]*api[^\"'<> ]*",
    "json urls": r"[^\"'<> ]+\.json\b",
    "login/member": r"(?i)log ?in|sign ?in|members? only|subscribe",
    "terms/scrap": r"(?i)scrap[a-z]*|crawl[a-z]*|automated (access|means)|robots",
}

session = requests.Session()
session.headers["User-Agent"] = USER_AGENT


def robots_for(url: str) -> urllib.robotparser.RobotFileParser:
    parts = urlparse(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    try:
        resp = session.get(robots_url, timeout=30)
        print(f"\n--- {robots_url} [{resp.status_code}]")
        text = resp.text if resp.ok else ""
        print("\n".join(text.splitlines()[:40]) or "(empty)")
        rp.parse(text.splitlines())
    except requests.RequestException as exc:
        print(f"robots.txt fetch failed: {exc}")
        rp.parse([])
    return rp


def describe(url: str, html: str) -> None:
    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    print(f"title: {title.group(1).strip()[:120] if title else '-'}")
    print(f"length: {len(html):,} chars; <tr>: {html.lower().count('<tr')}; <table>: {html.lower().count('<table')}")
    for label, pattern in PATTERNS.items():
        hits = Counter(m.group(0)[:120] for m in re.finditer(pattern, html))
        if hits:
            sample = ", ".join(f"{h} (x{n})" for h, n in hits.most_common(6))
            print(f"{label}: {sum(hits.values())} hits; e.g. {sample}")
    scripts = [urljoin(url, s) for s in re.findall(r"<script[^>]+src=[\"']([^\"']+)", html, re.I)]
    interesting = [s for s in scripts if re.search(r"(?i)table|ajax|data|api|app|chunk", s)]
    if interesting:
        print("scripts:", ", ".join(s[:120] for s in interesting[:8]))
    labels = re.findall(r"<b>\s*([A-Za-z ]{3,30}):\s*</b>", html)
    if labels:
        print("bold labels:", ", ".join(dict.fromkeys(labels)))


def main() -> None:
    for site, urls in SITES.items():
        print(f"\n================ {site} ================")
        robots = robots_for(urls[0])
        for url in urls:
            time.sleep(DELAY_S)
            allowed = robots.can_fetch(USER_AGENT, url)
            print(f"\n### {url}\nrobots.txt allows: {allowed}; crawl-delay: {robots.crawl_delay(USER_AGENT)}")
            if not allowed:
                continue
            try:
                resp = session.get(url, timeout=30)
            except requests.RequestException as exc:
                print(f"fetch failed: {exc}")
                continue
            print(f"status: {resp.status_code}; content-type: {resp.headers.get('content-type')}; final url: {resp.url}")
            if resp.ok and "html" in resp.headers.get("content-type", ""):
                describe(resp.url, resp.text)


if __name__ == "__main__":
    main()
