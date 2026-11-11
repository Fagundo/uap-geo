import pandas as pd
import yaml
from pathlib import Path

from uap_geo.classify.rules import RuleContext, build_rules
from uap_geo.classify.tiers import OutcomeTiers

ROOT = Path(__file__).resolve().parents[1]
CONFIG = yaml.safe_load((ROOT / "configs" / "filters.yaml").read_text())


def _ctx(rows):
    frame = pd.DataFrame(rows, columns=["summary", "local", "duration", "kp"])
    return RuleContext(
        text=frame["summary"].str.lower(),
        local_time=pd.to_datetime(frame["local"]),
        duration_s=frame["duration"].astype(float),
        kp_max=frame["kp"].astype(float),
    )


def _labels(rows, disabled=()):
    return OutcomeTiers(build_rules(CONFIG, disabled)).label_reports(_ctx(rows))


def test_every_configured_rule_has_an_implementation():
    assert len(build_rules(CONFIG)) == len(CONFIG["rules"])


def test_high_confidence_matches():
    labels = _labels([
        ["Several orange orbs drifting slowly and silently, rising one after another", "2012-07-04 22:00", 600, 2],
        ["Bright green aurora curtain over the mountains", "2015-03-17 23:00", 1800, 7.7],
        ["Bright fireball streak across the sky", "2010-08-12 23:30", 3, 2],
        ["Colored firework bursts then a red light", "2014-07-04 21:30", 120, 2],
        ["Odd light ((NUFORC Note: Possible Starlink satellites.  PD))", "2020-04-21 21:00", 300, 2],
    ])
    assert labels["explained_by"].tolist() == ["sky_lantern", "aurora", "meteor_fireball", "fireworks", "nuforc_note"]


def test_medium_matches_do_not_explain():
    labels = _labels([
        ["Orange orbs drifting slowly", "2012-05-10 22:00", 600, 2],           # lantern, not a holiday
        ["String of lights in a line moving north", "2020-04-21 21:00", 300, 2],  # Starlink without launch data
        ["Blinking red and green lights, like a plane but silent", "2015-01-01 03:00", 60, 2],
        ["A slow streak that lasted a minute", "2009-01-01 03:00", 60, 2],      # meteor words but long
        ["Glow low in the northern sky", "2009-01-01 03:00", 600, 3],           # northern glow, Kp too low
    ])
    assert labels["explained_by"].isna().all()
    assert labels["possible"].tolist() == [True, True, True, True, False]


def test_disabled_rule_is_skipped():
    labels = _labels([["Bright green aurora", "2015-03-17 23:00", 600, 7]], disabled=["aurora"])
    assert "aurora" not in labels.columns and labels["explained_by"].isna().all()


def test_event_tiers():
    reports = pd.DataFrame({"event_id": [0, 0, 1, 2]})
    labels = pd.DataFrame({"explained_by": ["aurora", None, None, None]})
    events = pd.DataFrame({"event_id": [0, 1, 2], "n_reports": [2, 1, 3], "max_duration_s": [60, 60, 30]})
    tiers = OutcomeTiers([]).tier_events(reports, labels, events).set_index("event_id")
    assert tiers["in_filtered"].tolist() == [False, True, True]
    assert tiers["in_high_quality"].tolist() == [False, False, True]
