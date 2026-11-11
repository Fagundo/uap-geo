"""Model validation: simulated matched data with a known rate ratio. Runs where statsmodels is installed (CI)."""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("statsmodels")

from uap_geo.hypotheses.designs.conditional_poisson import ConditionalPoissonTest  # noqa: E402


def _simulate(rate_ratio: float, n_strata: int = 3000, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_strata):
        base = rng.gamma(0.5, 0.4)                  # strong heterogeneity between places
        for night in range(9):                      # 1 exposed night, 8 controls, as in the storm design
            exposed = int(night == 0)
            moon = rng.uniform()
            mu = base * (rate_ratio ** exposed) * np.exp(0.2 * moon)
            rows.append((s, exposed, moon, rng.poisson(mu)))
    return pd.DataFrame(rows, columns=["stratum", "exposed", "moon", "count"])


def test_recovers_known_rate_ratio():
    result = ConditionalPoissonTest(group="stratum").fit(_simulate(1.3), ["exposed", "moon"])
    row = result.terms.loc["exposed"]
    assert row["ci_low"] < 1.3 < row["ci_high"]
    assert row["p_value"] < 0.05


def test_null_is_not_significant_most_of_the_time():
    rejections = 0
    for seed in range(20):
        result = ConditionalPoissonTest(group="stratum").fit(_simulate(1.0, n_strata=800, seed=seed), ["exposed", "moon"])
        rejections += result.p_value() < 0.05
    assert rejections <= 3   # about 1 expected at alpha 0.05


def test_collapsing_counties_gives_identical_estimate():
    """The storm test sums counts over counties within a storm; check equivalence on simulated data."""
    rng = np.random.default_rng(3)
    rows = []
    for storm in range(60):
        moons = rng.uniform(size=9)
        for county in range(25):
            base = rng.gamma(0.5, 0.3)
            for night in range(9):
                exposed = int(night == 0)
                rows.append((storm, f"{storm}_{county}", exposed, moons[night],
                             rng.poisson(base * 1.2 ** exposed * np.exp(0.3 * moons[night]))))
    data = pd.DataFrame(rows, columns=["storm", "stratum", "exposed", "moon", "count"])
    full = ConditionalPoissonTest(group="stratum").fit(data, ["exposed", "moon"]).terms
    collapsed_rows = data.groupby(["storm", "exposed", "moon"], as_index=False)["count"].sum()
    collapsed = ConditionalPoissonTest(group="storm").fit(collapsed_rows, ["exposed", "moon"]).terms
    assert np.allclose(full["rate_ratio"], collapsed["rate_ratio"], rtol=1e-3)


def test_dispersion_near_one_for_poisson_and_above_for_overdispersed():
    import numpy as np
    import pandas as pd

    from uap_geo.hypotheses.designs.conditional_poisson import ConditionalPoissonTest

    rng = np.random.default_rng(0)
    n, k = 3000, 9
    g = np.repeat(np.arange(n), k)
    exposed = np.tile([1] + [0] * (k - 1), n)
    base = rng.gamma(2.0, 1.0, n).repeat(k)
    pois = pd.DataFrame({"s": g, "exposed": exposed, "count": rng.poisson(base * 0.5)})
    over = pd.DataFrame({"s": g, "exposed": exposed, "count": rng.poisson(base * 0.5 * rng.gamma(0.5, 2.0, n * k))})
    test = ConditionalPoissonTest(group="s")
    assert 0.9 < test.fit(pois, ["exposed"]).dispersion < 1.1
    assert test.fit(over, ["exposed"]).dispersion > 1.5
