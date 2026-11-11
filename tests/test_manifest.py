import json

from uap_geo.common.manifest import RunManifest, sha256_file


def test_manifest_records_specs_and_inputs(tmp_path):
    spec = tmp_path / "H-test.yaml"
    spec.write_text("id: H-test\n")
    data = tmp_path / "raw" / "a.csv"
    data.parent.mkdir()
    data.write_text("x\n1\n")
    manifest = RunManifest(run_id="r1")
    digest = manifest.add_spec("H-test", spec)
    manifest.add_input_dir(tmp_path, tmp_path / "raw")
    out = json.loads(manifest.write(tmp_path / "manifest.json").read_text())
    assert out["specs"]["H-test"] == digest == sha256_file(spec)
    assert out["inputs"] == {"raw/a.csv": sha256_file(data)}
    assert out["run_id"] == "r1"
