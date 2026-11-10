"""Pure-pandas parsers for downloaded payloads (no GIS imports, so they are unit-testable anywhere)."""

from __future__ import annotations

import io
import json

import pandas as pd

from uap_geo.common.geo import COUNTY_ID


def parse_population(content: bytes) -> pd.DataFrame:
    text = content.decode("latin-1").lstrip("\ufeffï»¿ \n\r\t")
    if text.startswith("["):
        rows = json.loads(text)
        frame = pd.DataFrame(rows[1:], columns=rows[0])
        frame[COUNTY_ID] = frame["state"] + frame["county"]
        frame["population"] = pd.to_numeric(frame["P1_001N"], errors="coerce")
        return frame[[COUNTY_ID, "population"]]
    if text.upper().startswith("SUMLEV"):
        frame = pd.read_csv(io.StringIO(text), dtype={"SUMLEV": str, "STATE": str, "COUNTY": str})
        frame = frame.loc[frame["SUMLEV"] == "050"]
        column = next(c for c in ("POPESTIMATE2020", "ESTIMATESBASE2020", "CENSUS2020POP") if c in frame.columns)
        frame[COUNTY_ID] = frame["STATE"].str.zfill(2) + frame["COUNTY"].str.zfill(3)
        frame["population"] = pd.to_numeric(frame[column], errors="coerce")
        return frame[[COUNTY_ID, "population"]]
    raise ValueError(f"Unrecognised population payload: {text[:200]!r}")


def parse_nid(content: bytes, min_storage_acre_ft: float) -> pd.DataFrame:
    """National Inventory of Dams CSV -> lat, lon, storage for dams that impound a real reservoir.

    The export may start with a title line ("Last updated ...") and has used both camelCase
    (`latitude`, `nidStorage`) and display names (`Latitude`, `NID Storage (Acre-Ft)`), so the
    header row and columns are located by name rather than position.
    """
    text = content.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    header_at = next((i for i, line in enumerate(lines[:20]) if "latitude" in line.lower()), None)
    if header_at is None:
        raise ValueError(f"No latitude header in NID payload: {text[:200]!r}")
    frame = pd.read_csv(io.StringIO("\n".join(lines[header_at:])), low_memory=False)
    lower = {c.lower().replace(" ", ""): c for c in frame.columns}

    def pick(*candidates: str) -> str:
        for cand in candidates:
            for key, col in lower.items():
                if cand in key:
                    return col
        raise KeyError(f"None of {candidates} in NID columns {list(frame.columns)[:40]}")

    lat, lon = pick("latitude"), pick("longitude")
    storage = pick("normalstorage", "nidstorage", "maxstorage")
    out = pd.DataFrame(
        {
            "lat": pd.to_numeric(frame[lat], errors="coerce"),
            "lon": pd.to_numeric(frame[lon], errors="coerce"),
            "storage_acre_ft": pd.to_numeric(frame[storage], errors="coerce"),
        }
    ).dropna()
    return out.loc[out["storage_acre_ft"] >= min_storage_acre_ft].reset_index(drop=True)
