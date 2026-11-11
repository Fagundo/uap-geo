"""Build configs/celebrations/championships.yaml from Wikipedia infoboxes (run in GitHub Actions).

For each final from 2001 to 2023 (Super Bowl, World Series, NBA Finals, Stanley Cup Final) it reads
the event page's wikitext and records the deciding game's date (the end of the infobox date range),
the champion and the runner-up. Super Bowl infoboxes list home and visiting teams rather than a
champion, so Super Bowl winners and losers are given below and only the date is read.

    uv run python scripts/build_championships.py
"""

from __future__ import annotations

import re
import sys
import time
from datetime import date
from pathlib import Path

import requests
import yaml

RAW = "https://en.wikipedia.org/w/index.php?action=raw&redirect=yes&title={}"
PAGE = "https://en.wikipedia.org/wiki/{}"
HEADERS = {"User-Agent": "uap-geo-research/0.1 (+https://github.com/Fagundo/uap-geo)"}
YEARS = range(2001, 2024)
OUT = Path("configs/celebrations/championships.yaml")
TEAMS = Path("configs/celebrations/teams.yaml")

SUPER_BOWL = {  # year: (winner, loser)
    2001: ("Baltimore Ravens", "New York Giants"), 2002: ("New England Patriots", "St. Louis Rams"),
    2003: ("Tampa Bay Buccaneers", "Oakland Raiders"), 2004: ("New England Patriots", "Carolina Panthers"),
    2005: ("New England Patriots", "Philadelphia Eagles"), 2006: ("Pittsburgh Steelers", "Seattle Seahawks"),
    2007: ("Indianapolis Colts", "Chicago Bears"), 2008: ("New York Giants", "New England Patriots"),
    2009: ("Pittsburgh Steelers", "Arizona Cardinals"), 2010: ("New Orleans Saints", "Indianapolis Colts"),
    2011: ("Green Bay Packers", "Pittsburgh Steelers"), 2012: ("New York Giants", "New England Patriots"),
    2013: ("Baltimore Ravens", "San Francisco 49ers"), 2014: ("Seattle Seahawks", "Denver Broncos"),
    2015: ("New England Patriots", "Seattle Seahawks"), 2016: ("Denver Broncos", "Carolina Panthers"),
    2017: ("New England Patriots", "Atlanta Falcons"), 2018: ("Philadelphia Eagles", "New England Patriots"),
    2019: ("New England Patriots", "Los Angeles Rams"), 2020: ("Kansas City Chiefs", "San Francisco 49ers"),
    2021: ("Tampa Bay Buccaneers", "Kansas City Chiefs"), 2022: ("Los Angeles Rams", "Cincinnati Bengals"),
    2023: ("Kansas City Chiefs", "Philadelphia Eagles"),
}
# Dates used when a Super Bowl infobox date is in a format the parser does not read; from Wikipedia's
# "List of Super Bowl champions".
SUPER_BOWL_DATES = {2002: "2002-02-03", 2003: "2003-01-26", 2006: "2006-02-05", 2007: "2007-02-04",
                    2008: "2008-02-03", 2009: "2009-02-01"}
NO_FINAL = {("NHL", 2005)}  # NHL lockout season
MONTHS = {m: i for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August",
                                      "September", "October", "November", "December"], start=1)}


def roman(n: int) -> str:
    out = ""
    for value, sym in ((50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= value:
            out, n = out + sym, n - value
    return out


def titles(league: str, year: int) -> list[str]:
    if league == "NFL":
        n = year - 1966
        return [f"Super Bowl {n}" if n == 50 else f"Super Bowl {roman(n)}"]
    return {"MLB": [f"{year} World Series"], "NBA": [f"{year} NBA Finals"],
            "NHL": [f"{year} Stanley Cup Final", f"{year} Stanley Cup Finals"]}[league]


def clean(value: str) -> str:
    value = re.sub(r"<!--.*?-->", "", value)
    value = re.sub(r"<ref[^>]*/>", "", value)
    value = re.sub(r"<ref.*?</ref>", "", value)
    value = re.sub(r"<ref.*$", "", value)
    value = re.sub(r"\{\{nowrap\|([^}]*)\}\}", r"\1", value, flags=re.I)
    # {{start date|2001|1|28}} -> January 28, 2001; {{start-date|January 28, 2001}} -> January 28, 2001
    value = re.sub(r"\{\{start[ -]date\|(\d{4})\|(\d{1,2})\|(\d{1,2})[^}]*\}\}",
                   lambda m: f"{list(MONTHS)[int(m.group(2)) - 1]} {int(m.group(3))}, {m.group(1)}", value, flags=re.I)
    value = re.sub(r"\{\{start[ -]date\|([^}|]*)[^}]*\}\}", r"\1", value, flags=re.I)
    value = re.sub(r"\{\{[^}]*\}\}", "", value)
    value = value.replace("&nbsp;", " ").replace("<br />", " ").replace("<br>", " ")
    return value.strip()


def link_text(value: str) -> str:
    m = re.search(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", value)
    return (m.group(1) if m else clean(value)).strip()


def field(wikitext: str, *names: str) -> str | None:
    for name in names:
        m = re.search(rf"^\|\s*{name}\s*=\s*(.+)$", wikitext, flags=re.M | re.I)
        if m and clean(m.group(1)):
            return m.group(1)
    return None


def end_date(text: str, year: int) -> date:
    text = clean(text)
    text = re.sub(r",?\s*\d{4}", "", text).strip()
    last = re.split(r"\s*[–—-]\s*", text)[-1].strip()
    if re.fullmatch(r"\d{1,2}", last):
        month = next(m for m in MONTHS if m in text)
        return date(year, MONTHS[month], int(last))
    m = re.match(r"([A-Z][a-z]+)\s+(\d{1,2})", last)
    return date(year, MONTHS[m.group(1)], int(m.group(2)))


def fetch(title: str) -> str | None:
    resp = requests.get(RAW.format(title.replace(" ", "_")), headers=HEADERS, timeout=60)
    time.sleep(0.5)
    return resp.text if resp.status_code == 200 and resp.text.strip() else None


def main() -> int:
    known = yaml.safe_load(TEAMS.read_text())["teams"]
    rows, problems = [], []
    for league in ("NFL", "MLB", "NBA", "NHL"):
        for year in YEARS:
            text, title = None, None
            for title in titles(league, year):
                text = fetch(title)
                if text:
                    break
            if (league, year) in NO_FINAL:
                print(f"{league} {year}: no final (skipped)")
                continue
            if not text:
                problems.append(f"{league} {year}: no page ({titles(league, year)})")
                continue
            raw_date = field(text, "date", "dates")
            if league == "NFL":
                winner, loser = SUPER_BOWL[year]
            elif league == "NHL":
                teams = [link_text(field(text, f"team{i}") or "").strip("'") for i in (1, 2)]
                totals = [int(re.sub(r"\D", "", clean(field(text, f"team{i}_tot") or "0")) or 0) for i in (1, 2)]
                if not all(teams) or max(totals) != 4:
                    problems.append(f"NHL {year}: teams {teams} totals {totals}")
                    continue
                winner, loser = (teams[0], teams[1]) if totals[0] == 4 else (teams[1], teams[0])
            else:
                champ, runner = field(text, "champion", "winner"), field(text, "runnerup", "runner-up", "runner_up", "loser")
                if not champ or not runner:
                    problems.append(f"{league} {year}: champion/runner-up not found")
                    continue
                winner, loser = link_text(champ), link_text(runner)
                winner, loser = (re.sub(r"\s*\(\d\)$", "", t) for t in (winner, loser))
            try:
                if league == "NFL" and year in SUPER_BOWL_DATES and not (raw_date and clean(raw_date)):
                    deciding = date.fromisoformat(SUPER_BOWL_DATES[year])
                else:
                    deciding = end_date(raw_date, year)
            except Exception as exc:
                problems.append(f"{league} {year}: date '{raw_date}' not parsed ({exc})")
                continue
            for team in (winner, loser):
                if team not in known:
                    problems.append(f"{league} {year}: team '{team}' missing from {TEAMS}")
            rows.append({"league": league, "year": year, "date": deciding.isoformat(), "winner": winner, "loser": loser,
                         "source": PAGE.format(title.replace(" ", "_"))})
            print(f"{league} {year} {deciding} {winner} def. {loser}")
    header = ("# Deciding-game dates, champions and runners-up, 2001-2023, read from Wikipedia infoboxes by\n"
              "# scripts/build_championships.py (Super Bowl teams given in the script). Frozen once H-celebrate-01\n"
              "# is registered; its implementation notes record this file's SHA-256.\n")
    OUT.write_text(header + yaml.safe_dump({"finals": rows}, sort_keys=False, allow_unicode=True))
    print(f"\n{len(rows)} finals written to {OUT}")
    for p in problems:
        print("PROBLEM:", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
