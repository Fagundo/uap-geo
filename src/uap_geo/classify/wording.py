"""Date-free wording matches shared by studies and the residual set."""

from __future__ import annotations

import pandas as pd

from uap_geo.classify.rules import contains_any


def lantern_like(text: pd.Series, filters: dict, colour_words: tuple[str, ...] = ()) -> pd.Series:
    """Lantern, fireworks or fire-coloured-light wording, judged the same way on every night (no date condition)."""
    groups = filters["rules"]["sky_lantern"]["text_all_groups"]
    lantern = pd.Series(True, index=text.index)
    for words in groups:
        lantern &= contains_any(text, words)
    out = lantern | contains_any(text, filters["rules"]["fireworks"]["text_any"])
    return out | contains_any(text, colour_words) if colour_words else out
