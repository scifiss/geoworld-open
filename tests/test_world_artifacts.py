import json
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from geoworld_open.cli import app
from geoworld_open.domains.geoscience.structural import run_structural_world
from geoworld_open.specs import load_geospec
from geoworld_open.world_artifacts import (
    verify_world_artifact_checksums,
    write_world_artifacts,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "scenarios" / "structural_multifault.yaml"


def test_world_artifacts_are_complete_and_checksums_validate(tmp_path) -> None:
    result = run_structural_world(load_geospec(EXAMPLE))
    output = write_world_artifacts(result, tmp_path / "world-run")
    required = {
        "world.json", "world_summary.json", "dataset_metadata.json",
        "execution_plan.json", "trace.json", "diagnostics.json", "provenance.json",
        "structure_diagnostic.png", "report.md", "manifest.json",
    }
    assert required <= {item.name for item in output.iterdir()}
    assert (output / "inputs" / "structural-input.json").is_file()
    assert (output / "inputs" / "structural-input.yaml").is_file()
    assert (output / "arrays" / "porosity.npy").is_file()
    assert (output / "arrays" / "fault_selection.npy").is_file()
    assert (output / "coordinates" / "depth.npy").is_file()
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["workflow"] == "structural-world"
    assert manifest["initial_state_id"] == "state:structural-initial"
    assert manifest["final_state_id"] == "state:structural-final"
    verify_world_artifact_checksums(output)

    np.save(output / "arrays" / "porosity.npy", np.zeros((1, 1)), allow_pickle=False)
    with pytest.raises(ValueError, match="checksum mismatch"):
        verify_world_artifact_checksums(output)


def test_world_run_cli_uses_new_path_without_changing_legacy_run(tmp_path) -> None:
    output = tmp_path / "cli-world"
    result = CliRunner().invoke(
        app,
        ["world-run", str(EXAMPLE), "--output", str(output)],
    )
    assert result.exit_code == 0, result.output
    assert "state:structural-initial -> state:structural-final" in result.output
    assert (output / "manifest.json").is_file()


def test_world_artifact_content_hashes_repeat(tmp_path) -> None:
    result = run_structural_world(load_geospec(EXAMPLE))
    first = write_world_artifacts(result, tmp_path / "first")
    second = write_world_artifacts(result, tmp_path / "second")
    first_manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    second_manifest = json.loads((second / "manifest.json").read_text(encoding="utf-8"))
    assert (
        first_manifest["structural_input_sha256"]
        == second_manifest["structural_input_sha256"]
    )
    assert first_manifest["representation_hashes"] == second_manifest["representation_hashes"]
    assert first_manifest["numerical_dataset_sha256"] == second_manifest["numerical_dataset_sha256"]
    assert {item["path"]: item["sha256"] for item in first_manifest["artifacts"]} == {
        item["path"]: item["sha256"] for item in second_manifest["artifacts"]
    }
