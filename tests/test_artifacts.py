import hashlib
import json

import numpy as np

from geoworld_open.artifacts import write_artifacts
from geoworld_open.workflow import run_workflow


def test_complete_artifact_set(tmp_path, layered_scenario) -> None:
    output = write_artifacts(run_workflow(layered_scenario), tmp_path / "run")
    required = {
        "scenario.yaml",
        "summary.png",
        "report.md",
        "trace.json",
        "manifest.json",
    }
    assert required <= {path.name for path in output.iterdir()}
    assert (output / "arrays" / "vp_m_s.npy").is_file()
    assert (output / "arrays" / "avo_stack_low.npy").is_file()

    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["software"]["name"] == "geoworld-open"
    assert manifest["seed"] == layered_scenario.seed
    assert len(manifest["operators"]) == 4
    for artifact in manifest["artifacts"]:
        path = output / artifact["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
    assert np.load(output / "arrays" / "vp_m_s.npy", allow_pickle=False).shape == (100, 160)


def test_scientific_artifact_hashes_repeat(tmp_path, layered_scenario) -> None:
    first = write_artifacts(run_workflow(layered_scenario), tmp_path / "first")
    second = write_artifacts(run_workflow(layered_scenario), tmp_path / "second")
    first_manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    second_manifest = json.loads((second / "manifest.json").read_text(encoding="utf-8"))
    first_hashes = {
        item["path"]: item["sha256"] for item in first_manifest["artifacts"] if item["deterministic"]
    }
    second_hashes = {
        item["path"]: item["sha256"] for item in second_manifest["artifacts"] if item["deterministic"]
    }
    assert first_manifest["scenario_sha256"] == second_manifest["scenario_sha256"]
    assert first_hashes == second_hashes
