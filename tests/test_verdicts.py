import pandas as pd

from uap_geo.hypotheses.base import EventStudy, TestOutcome
from uap_geo.hypotheses.designs.conditional_poisson import TestResult

POWER = {"rate_ratio": 1.10, "alpha": 0.05, "underpowered_below": 0.50, "refute_requires": 0.80}


class _Study(EventStudy):
    def __init__(self, split):  # no files needed for verdict logic
        self.split = split
        self.impl = {"parameters": {"power": POWER}}

    def analyse(self):
        raise NotImplementedError


def _outcome(name, rr, lo, hi, p, power, check):
    terms = pd.DataFrame({"rate_ratio": [rr], "ci_low": [lo], "ci_high": [hi], "p_value": [p]},
                         index=pd.Index(["exposed"], name="term"))
    o = TestOutcome(name, {"filtered": TestResult(terms, 10, 100, 0.1)}, {"c": {"holds": check}}, power)
    return o


def test_verdict_order():
    outs = [_outcome("big", 2.8, 2.3, 3.4, 1e-20, 0.11, True),     # significant but low power for 1.10
            _outcome("null", 1.0, 0.94, 1.05, 0.9, 0.92, False),
            _outcome("weak", 1.1, 0.9, 1.3, 0.3, 0.25, False),
            _outcome("mid", 1.05, 0.9, 1.2, 0.5, 0.65, False)]
    _Study("confirm")._verdicts(outs)
    assert [o.verdict for o in outs] == ["confirmed", "refuted", "underpowered", "inconclusive"]
