import json
from pathlib import Path

from uap_geo.common.config import Config
from uap_geo.common.download import filename_from_url
from uap_geo.data.scraping.nuforc import join_places, read_report_json

ROOT = Path(__file__).resolve().parents[1]


def test_config_loads_and_marks_unconfigured_rasters_inactive():
    config = Config.from_yaml(ROOT / "configs" / "v1.yaml", root=ROOT)
    assert config.study.start_year == 2001
    assert config.source("faults").is_active
    assert not config.source("light_pollution").is_active
    assert "fault_length_per_km2" in config.models.geology


def test_join_places_matches_on_city_state_country():
    import pandas as pd

    sightings = pd.DataFrame({"city": ["Salem", "Salem"], "state": ["OR", "MA"], "country_code": ["US", "US"]})
    places = pd.DataFrame(
        {
            "city": ["Salem", "Salem"],
            "state": ["MA", "OR"],
            "country_code": ["US", "US"],
            "latitude": [42.5, 44.9],
            "longitude": [-70.9, -123.0],
        }
    )
    out = join_places(sightings, places)
    assert list(out["latitude"]) == [44.9, 42.5]


def test_filename_from_url():
    assert filename_from_url("https://x.org/a/b/file.zip") == "file.zip"
    assert filename_from_url("https://sb.gov/file/get/123?name=Qfaults_GIS.zip") == "Qfaults_GIS.zip"


def test_auth_headers_only_for_huggingface_with_token(monkeypatch):
    from uap_geo.common.download import auth_headers

    monkeypatch.delenv("HF_TOKEN", raising=False)
    assert auth_headers("https://huggingface.co/x") == {}
    monkeypatch.setenv("HF_TOKEN", "abc")
    assert auth_headers("https://huggingface.co/x") == {"Authorization": "Bearer abc"}
    assert auth_headers("https://census.gov/x") == {}


def test_read_report_json_layouts(tmp_path):
    records = [{"Occurred": "2010-01-01", "Location": "A, WA, USA"}]
    as_list = tmp_path / "list.json"
    as_list.write_text(json.dumps(records))
    as_dict = tmp_path / "dict.json"
    as_dict.write_text(json.dumps({"r1": records[0]}))
    as_lines = tmp_path / "lines.json"
    as_lines.write_text("\n".join(json.dumps(r) for r in records * 2))
    assert len(read_report_json(as_list)) == 1
    assert read_report_json(as_dict).loc[0, "report_id"] == "r1"
    assert len(read_report_json(as_lines)) == 2
