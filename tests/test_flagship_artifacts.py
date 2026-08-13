import csv
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from geoworld_open.cli import app
from geoworld_open.domains.geoscience.flagship import (
    FlagshipSpec,
    load_flagship_spec,
    run_flagship_world,
    verify_flagship_artifacts,
    write_flagship_artifacts,
)
from geoworld_open.world_artifacts import file_sha256


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "scenarios" / "flagship_faulted_reservoir.yaml"


def _result():
    return run_flagship_world(load_flagship_spec(EXAMPLE))


def test_flagship_artifacts_are_complete_and_semantically_verified(tmp_path) -> None:
    result = _result()
    output = write_flagship_artifacts(result, tmp_path / "flagship")
    required = {
        "inputs/flagship-input.json",
        "wells/flagship-well-trajectory.csv",
        "observations/well-pressure.csv",
        "observations/well-pressure.json",
        "world_graph.json",
        "state_lineage.json",
        "assumptions.md",
        "flagship_execution.json",
        "flagship_diagnostic.png",
        "flagship_public.png",
        "manifest.json",
    }
    found = {str(item.relative_to(output)) for item in output.rglob("*") if item.is_file()}
    assert required <= found
    verify_flagship_artifacts(output)

    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    listed = {item["path"] for item in manifest["artifacts"]}
    assert listed == found - {"manifest.json"}
    assert manifest["observation_id"] == "observation:flagship-well-pressure"
    graph = json.loads((output / "world_graph.json").read_text(encoding="utf-8"))
    assert graph["semantic_distinctions"]["Fault"].startswith("persistent Entity")
    lineage = json.loads((output / "state_lineage.json").read_text(encoding="utf-8"))
    assert lineage["lineage"] == [
        "state:structural-final",
        "state:flagship-baseline",
        "state:flagship-perturbed",
    ]
    with (output / "observations" / "well-pressure.csv").open(
        encoding="utf-8",
        newline="",
    ) as stream:
        rows = list(csv.DictReader(stream))
    assert tuple(rows[0]) == (
        "well_id",
        "requested_depth_m",
        "requested_x_m",
        "sampled_depth_m",
        "sampled_x_m",
        "model_time_days",
        "true_model_pressure_pa",
        "noise_pa",
        "observed_pressure_pa",
    )
    assert [float(row["requested_depth_m"]) for row in rows] == [190.0, 240.0, 290.0]
    assert [float(row["sampled_depth_m"]) for row in rows] == [187.5, 237.5, 287.5]
    assert {float(row["requested_x_m"]) for row in rows} == {700.0}
    assert {float(row["sampled_x_m"]) for row in rows} == {695.0}


def test_observation_semantic_hash_is_independent_of_file_checksum(tmp_path) -> None:
    output = write_flagship_artifacts(_result(), tmp_path / "flagship")
    evidence = output / "observations" / "well-pressure.csv"
    evidence.write_text(evidence.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    item = next(entry for entry in manifest["artifacts"] if entry["path"] == "observations/well-pressure.csv")
    item["sha256"] = file_sha256(evidence)
    item["bytes"] = evidence.stat().st_size
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    with pytest.raises(ValueError, match="Representation content hash mismatch"):
        verify_flagship_artifacts(output)


def test_flagship_diagnostic_output_option_is_honored(tmp_path) -> None:
    spec = load_flagship_spec(EXAMPLE)
    payload = spec.model_dump(mode="python")
    payload["outputs"]["save_diagnostic_figure"] = False
    result = run_flagship_world(FlagshipSpec.model_validate(payload))
    output = write_flagship_artifacts(result, tmp_path / "minimal")
    assert not (output / "flagship_diagnostic.png").exists()
    assert not (output / "flagship_public.png").exists()
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert {"flagship_diagnostic.png", "flagship_public.png"}.isdisjoint({
        item["path"] for item in manifest["artifacts"]
    })
    verify_flagship_artifacts(output)


def test_flagship_cli_runs_end_to_end(tmp_path) -> None:
    output = tmp_path / "cli-flagship"
    invocation = CliRunner().invoke(
        app,
        ["flagship-run", str(EXAMPLE), "--output", str(output)],
    )
    assert invocation.exit_code == 0, invocation.output
    assert "state:flagship-baseline -> state:flagship-perturbed" in invocation.output
    verify_flagship_artifacts(output)
