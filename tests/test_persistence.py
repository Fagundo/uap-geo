import numpy as np
import pandas as pd

from uap_geo.evaluation.power import nb_regression_power
from uap_geo.hypotheses.persistence import neighbour_mean, shrunken_log_excess
from uap_geo.training.models import ModelSpec, NegBinRateModel


def test_shrinkage_pulls_small_counts_toward_zero():
    obs, exp = pd.Series([2.0, 200.0]), pd.Series([1.0, 100.0])
    ex = shrunken_log_excess(obs, exp, dispersion=0.5)
    assert 0 < ex[0] < np.log(2) and abs(ex[1] - np.log(2)) < 0.02


def test_neighbour_mean_excludes_self():
    xy = np.array([[0, 0], [1, 0], [2, 0], [10, 0]], float)
    out = neighbour_mean(pd.Series([1.0, 2.0, 3.0, 100.0]), xy, k=1)
    assert out.tolist() == [2.0, 1.0, 2.0, 3.0]


def test_power_grows_with_events():
    assert nb_regression_power(1000, 3000, 0.5, 1.10) < nb_regression_power(50000, 3000, 0.5, 1.10)
    assert nb_regression_power(60000, 3000, 0.5, 1.10) > 0.99


def test_persistence_recovered_by_two_period_design():
    rng = np.random.default_rng(0)
    n = 1500
    frailty = rng.gamma(4.0, 0.25, n)                 # stable county trait, mean 1
    x = rng.normal(size=n)
    pop = rng.lognormal(10, 1, n)
    state = rng.integers(0, 20, n).astype(str)
    mu = pop / 2e4 * np.exp(0.2 * x)
    a = pd.DataFrame({"x": x, "state": state, "population": pop})
    ya, yb = rng.poisson(mu * frailty), rng.poisson(mu * frailty)
    fit_a = NegBinRateModel(ModelSpec("a", ("x",), ("state",)), quiet=True).fit(a.assign(report_count=ya))
    excess = shrunken_log_excess(pd.Series(ya).reindex(fit_a.fitted.index), fit_a.fitted, fit_a.alpha)
    b = a.assign(report_count=yb, excess_prior=excess)
    fit_b = NegBinRateModel(ModelSpec("b", ("x", "excess_prior"), ("state",)), quiet=True, cluster="state").fit(b)
    assert fit_b.rate_ratio("excess_prior") > 1.2 and fit_b.coefficients.loc["excess_prior", "p_value"] < 0.001
    # no persistence when the second period has fresh frailty
    yb0 = rng.poisson(mu * rng.gamma(4.0, 0.25, n))
    fit_0 = NegBinRateModel(ModelSpec("b", ("x", "excess_prior"), ("state",)), quiet=True, cluster="state").fit(
        a.assign(report_count=yb0, excess_prior=excess))
    c = fit_0.coefficients.loc["excess_prior"]
    assert c["ci_low"] < 1.06 and c["ci_high"] > 0.94


def test_acs_table_reads_county_rows_only():
    from uap_geo.data.scraping.acs import read_acs_counties

    text = ("GEO_ID|B25004_E006|B25004_M006\n0100000US|5092152|40323\n0400000US53|90000|1000\n"
            "0500000US53055|7000|300\n0500000US37055|30000|900\n")
    out = read_acs_counties(text, ["B25004_E006"])
    assert out.iloc[:, 0].tolist() == ["53055", "37055"] and out["B25004_E006"].tolist() == [7000, 30000]
