"""Parquet persistence for intermediate and processed tables."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


class TableStore:
    """Reads and writes named tables as Parquet (GeoParquet when the frame has geometry)."""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.folder.mkdir(parents=True, exist_ok=True)

    def path(self, name: str) -> Path:
        return self.folder / f"{name}.parquet"

    def exists(self, name: str) -> bool:
        return self.path(name).exists()

    def save(self, name: str, frame: pd.DataFrame) -> Path:
        path = self.path(name)
        frame.to_parquet(path, index=False)
        return path

    def load(self, name: str) -> pd.DataFrame:
        return pd.read_parquet(self.path(name))

    def load_geo(self, name: str):
        import geopandas as gpd

        return gpd.read_parquet(self.path(name))
