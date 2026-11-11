"""Power for a matched (conditional) Poisson comparison, from total event counts only."""

from __future__ import annotations

import math
from statistics import NormalDist


def conditional_poisson_power(total_events: float, exposed_share: float, rate_ratio: float = 1.10,
                              alpha: float = 0.05) -> float:
    """Approximate power to detect `rate_ratio` when `total_events` fall in informative strata and a
    share `exposed_share` of the observed time is exposed. Uses only the total, never the
    exposed-versus-control split, so it cannot leak the answer.

    Conditional on the stratum total, exposed events ~ Binomial(n, q) with q = p*RR / (p*RR + 1 - p).
    The log rate ratio estimate has SE ~ 1 / sqrt(n * p * (1 - p)).
    """
    if total_events <= 0 or not 0 < exposed_share < 1:
        return 0.0
    se = 1.0 / math.sqrt(total_events * exposed_share * (1 - exposed_share))
    z = NormalDist().inv_cdf(1 - alpha / 2)
    shift = math.log(rate_ratio) / se
    return (1 - NormalDist().cdf(z - shift)) + NormalDist().cdf(-z - shift)
