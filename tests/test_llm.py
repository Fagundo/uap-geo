import json
from types import SimpleNamespace

import pandas as pd

from uap_geo.llm.extractor import FeatureExtractor
from uap_geo.llm.schema import TOOL
from uap_geo.llm.strangeness import feature_table, score
from uap_geo.llm.validation import group_masks, stratified_sample

FEATURES = {"object_count": 1, "shapes": ["disc"], "colours": ["white"], "light_pattern": "steady",
            "motions": ["hovered_then_moved", "sudden_acceleration"], "speed": "extremely_fast", "sound": "silent",
            "apparent_distance": "near", "witness_count": 2, "evidence": ["none_stated"],
            "physical_effects": ["none_stated"], "detail": "detailed",
            "conventional_likelihood": {k: 0.1 for k in TOOL["input_schema"]["properties"]["conventional_likelihood"]["required"]}}


class FakeMessages:
    def __init__(self):
        self.calls = []

    def create(self, **params):
        self.calls.append(params)
        return SimpleNamespace(content=[SimpleNamespace(type="tool_use", input=FEATURES)])


def test_extract_is_blinded_and_structured():
    client = SimpleNamespace(messages=FakeMessages())
    rows = pd.DataFrame({"report_id": ["a"], "text": ["silent disc hovered then shot away"], "duration_s": [30.0]})
    out = FeatureExtractor("test-model", client=client).extract(rows)
    params = client.messages.calls[0]
    assert params["tool_choice"] == {"type": "tool", "name": "record_features"}
    content = params["messages"][0]["content"]
    assert "30 seconds" in content and "silent disc" in content
    assert json.loads(out.loc[0, "features"])["shapes"] == ["disc"]


def test_strangeness_score():
    assert score(FEATURES) == 2 + 1 + 1 + 0 + 1          # two odd motions, disc, silent and near, nothing ordinary
    dull = dict(FEATURES, motions=["straight_steady"], shapes=["point_of_light"], sound="not_stated",
                conventional_likelihood={"aircraft": 0.9})
    assert score(dull) == 0
    table = feature_table(pd.DataFrame({"report_id": ["a"], "features": [json.dumps(FEATURES)]}))
    assert bool(table.loc[0, "high_strangeness"]) and table.loc[0, "p_aircraft"] == 0.1


def test_groups_and_sample():
    residual = pd.DataFrame({"report_id": list("abcdef"), "text": ["x"] * 6,
                             "reasons": ["launch_window", "nuforc_note", "lantern_wording,holiday_night", "", "", "meteor_fireball"],
                             "tier": ["explained", "explained", "possible", "residual", "residual", "explained"]})
    masks = group_masks(residual)
    assert masks["launch window"].tolist() == [True, False, False, False, False, False]
    assert masks["NUFORC-identified"].sum() == 1 and masks["holiday night"].sum() == 1
    assert masks["residual (no match)"].sum() == 2
    assert len(stratified_sample(residual, per_group=1, residual_n=2)) == 6


def test_v2_prompt_adds_cause_guide():
    v1 = FeatureExtractor("m", schema="features-v1").params("x", 1.0)["system"][0]["text"]
    v2 = FeatureExtractor("m", schema="features-v2").params("x", 1.0)["system"][0]["text"]
    assert v2.startswith(v1) and "jellyfish" in v2 and "jellyfish" not in v1
