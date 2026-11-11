import pandas as pd

from uap_geo.classify.validation import FilterSample, FilterValidation, report_ids


def _reports(n=10):
    return pd.DataFrame({
        "occurred_utc": pd.date_range("2010-01-01", periods=n, freq="D"),
        "city": ["A"] * n, "state": ["WA"] * n,
        "summary": [f"summary {i}" for i in range(n)],
        "local_time": pd.date_range("2010-01-01", periods=n, freq="D"),
        "duration_s": [60.0] * n,
    })


def test_report_ids_are_stable_and_unique():
    reports = _reports()
    assert report_ids(reports).tolist() == report_ids(reports.copy()).tolist()
    assert report_ids(reports).nunique() == 10


def test_sample_and_precision(tmp_path):
    reports = _reports()
    labels = pd.DataFrame({"explained_by": ["aurora", "aurora", "meteor_fireball"] + [None] * 7})
    sample = FilterSample(per_rule=5, random=3, seed=1).draw(reports, labels)
    assert set(sample.loc[sample["rule"].notna(), "rule"]) == {"aurora", "meteor_fireball"}
    ids = sample.set_index("rule", drop=False)
    truth = []
    for _, row in sample.iterrows():
        truth.append((row["report_id"], row["rule"] if row["rule"] == "aurora" else "none"))
    path = tmp_path / "labels.csv"
    pd.DataFrame(truth, columns=["report_id", "label"]).to_csv(path, index=False)
    table = FilterValidation().precision(sample, path)
    assert table.loc["aurora", "precision"] == 1.0 and table.loc["aurora", "passes"]
    assert table.loc["meteor_fireball", "precision"] == 0.0
