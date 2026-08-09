import json
from pathlib import Path

from geoworld_open.artifacts import write_structural_artifacts
from geoworld_open.science import run_structural_workflow


def test_phase2_artifact_and_provenance_contract(tmp_path, structural_v2_scenario) -> None:
    output = write_structural_artifacts(
        run_structural_workflow(structural_v2_scenario), tmp_path / "phase2"
    )
    expected = {
        "geospec_v2.yaml",
        "dataset_metadata.json",
        "trace.json",
        "manifest.json",
        "report.md",
        "structure_diagnostic.png",
    }
    assert expected <= {path.name for path in output.iterdir()}
    assert (output / "arrays" / "facies.npy").is_file()
    assert (output / "coordinates" / "depth.npy").is_file()
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["geospec_schema_version"] == "2.0"
    assert manifest["software"]["name"] == "geoworld-open"
    assert manifest["seed_lineage"]["root_seed"] == structural_v2_scenario.seed
    assert manifest["scientific_hashes"]["dataset_sha256"]
    assert manifest["dataset"]["coordinates"]["depth"]["metadata"]["units"] == "m"
    serialized = json.dumps(manifest)
    assert "/home/" not in serialized
    assert "gaor" not in serialized


def test_scientific_hashes_repeat(tmp_path, structural_v2_scenario) -> None:
    result = run_structural_workflow(structural_v2_scenario)
    first = write_structural_artifacts(result, tmp_path / "first")
    second = write_structural_artifacts(result, tmp_path / "second")
    first_manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    second_manifest = json.loads((second / "manifest.json").read_text(encoding="utf-8"))
    assert first_manifest["normalized_input_sha256"] == second_manifest["normalized_input_sha256"]
    assert first_manifest["scientific_hashes"] == second_manifest["scientific_hashes"]


def test_diagnostic_figure_is_nonempty(tmp_path, structural_v2_scenario) -> None:
    output = write_structural_artifacts(
        run_structural_workflow(structural_v2_scenario), tmp_path / "phase2"
    )
    figure = Path(output / "structure_diagnostic.png")
    assert figure.stat().st_size > 10_000
