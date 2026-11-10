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
