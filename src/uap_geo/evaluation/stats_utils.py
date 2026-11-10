"""Small pandas/numpy statistics helpers (no GIS or statsmodels imports)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def benjamini_hochberg(p_values: pd.Series) -> pd.Series:
    """False-discovery-rate adjusted p-values (Benjamini–Hochberg step-up), same index as input."""
    p = p_values.astype(float)
    n = len(p)
    if n == 0:
        return p
    order = np.argsort(p.to_numpy())
    ranked = p.to_numpy()[order] * n / np.arange(1, n + 1)
    adjusted = np.minimum.accumulate(ranked[::-1])[::-1].clip(max=1.0)
    out = np.empty(n)
    out[order] = adjusted
    return pd.Series(out, index=p.index, name="p_bh")


def variance_inflation(frame: pd.DataFrame) -> pd.Series:
    """VIF per column = diagonal of the inverse correlation matrix. Above ~5 means a covariate is
    largely explained by the others, so its own coefficient is poorly identified."""
    data = frame.dropna()
    data = data.loc[:, data.std(ddof=0) > 0]
    corr = np.corrcoef(data.to_numpy(), rowvar=False)
    vif = np.diag(np.linalg.pinv(corr))
    return pd.Series(vif, index=data.columns, name="vif")
