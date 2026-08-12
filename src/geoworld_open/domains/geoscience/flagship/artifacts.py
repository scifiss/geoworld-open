"""Reproducible artifacts for the flagship semantic World demonstration."""

from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path
from typing import Any

from geoworld_open import __version__
from geoworld_open.domains.geoscience.flagship.diagnostics import (
    save_flagship_diagnostic,
)
from geoworld_open.domains.geoscience.flagship.integration import (
    BASELINE_STATE_ID,
    PERTURBED_STATE_ID,
    STRUCTURAL_STATE_ID,
    FlagshipWorldResult,
)
from geoworld_open.world import RepresentationKind, dataset_content_sha256
from geoworld_open.world_artifacts import (
    artifact_relative_path,
    file_sha256,
    load_representation_dataset,
    write_representation_bundle,
    write_world_artifacts,
)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _world_graph(result: FlagshipWorldResult) -> dict[str, Any]:
    return {
        "world_id": result.world.world_id,
        "entities": [
            {
                "entity_id": item.entity_id,
                "entity_type": item.entity_type,
                "label": item.label,
            }
            for item in result.world.entities
        ],
        "relations": [
            {
                "relation_id": item.relation_id,
                "source_entity_id": item.source_entity_id,
                "relation_type": item.relation_type,
                "target_entity_id": item.target_entity_id,
            }
            for item in result.world.relations
        ],
        "representations": [
            {
                "representation_id": item.representation_id,
                "version": item.version,
                "kind": item.kind.value,
                "subjects": [subject.model_dump(mode="json") for subject in item.subjects],
                "artifact_uri": item.artifact_uri,
            }
            for item in result.world.representations
        ],
        "semantic_distinctions": {
            "Fault": "persistent Entity; fault_selection is a derived numerical Field",
            "Well": "persistent Entity; its trajectory is a CURVE Representation",
            "ReservoirRegion": (
                "persistent named Entity; reservoir_selection is a Boolean Field"
            ),
        },
    }


def _state_lineage(result: FlagshipWorldResult) -> dict[str, Any]:
    selected = (STRUCTURAL_STATE_ID, BASELINE_STATE_ID, PERTURBED_STATE_ID)
    states = {item.state_id: item for item in result.world.states}
    return {
        "lineage": list(selected),
        "states": [
            {
                "state_id": states[state_id].state_id,
                "parent_state_id": states[state_id].parent_state_id,
                "role": states[state_id].role.value,
                "valid_from": (
                    states[state_id].valid_from.model_dump(mode="json")
                    if states[state_id].valid_from
                    else None
                ),
                "field_binding_ids": list(states[state_id].field_binding_ids),
                "representation_refs": [
                    item.model_dump(mode="json")
                    for item in states[state_id].representation_refs
                ],
                "provenance_ids": list(states[state_id].provenance_ids),
            }
            for state_id in selected
        ],
        "time_note": (
            "Relative model time indexes synthetic benchmark states; the analytic "
            "perturbation is not a time-integrated flow solution."
        ),
    }


def _assumptions_markdown(result: FlagshipWorldResult) -> str:
    structural = result.flagship_input.structural
    baseline = result.flagship_input.baseline
    perturbation = result.flagship_input.perturbation
    observation = result.flagship_input.observation
    lines = [
        "# Flagship assumptions",
        "",
        "## Structural assumptions",
        "",
        *[f"- {item}" for item in structural.assumptions],
        "",
        "## Pressure assumptions",
        "",
        "- Illustrative hydrostatic baseline: `p0(z) = p_ref + rho_ref * g * (z - z_ref)`.",
        f"- `p_ref = {baseline.pressure_reference_pa:g} Pa`.",
        f"- `z_ref = {baseline.pressure_reference_depth_m:g} m`.",
        f"- `rho_ref = {baseline.reference_density_kg_m3:g} kg/m3`.",
        f"- `g = {baseline.gravity_m_s2:g} m/s2`.",
        "- Pressure is not calibrated formation pressure.",
        "",
        "## Temperature assumptions",
        "",
        "- Linear benchmark: `T0(z) = T_ref + G * (z - z_ref)`.",
        f"- `T_ref = {baseline.temperature_reference_deg_c:g} degC`.",
        f"- `G = {baseline.geothermal_gradient_deg_c_per_m:g} degC/m`.",
        "- No heat transport is modeled.",
        "",
        "## Perturbation assumptions",
        "",
        "- Analytic Gaussian-like pressure change multiplied by reservoir_selection.",
        f"- Maximum change is `{perturbation.maximum_delta_pressure_pa:g} Pa`.",
        f"- Center is `({perturbation.center_x_m:g}, {perturbation.center_depth_m:g}) m`.",
        f"- Sigma is `({perturbation.sigma_x_m:g}, {perturbation.sigma_depth_m:g}) m`.",
        "- This is not reservoir simulation or pressure diffusion.",
        "- No mass conservation, permeability, relative permeability, or fluid transport is modeled.",
        "",
        "## Observation assumptions",
        "",
        f"- Sampling method: `{observation.sampling_method}`.",
        f"- Gaussian noise sigma: `{observation.noise_sigma_pa:g} Pa`.",
        f"- Explicit noise seed: `{observation.noise_seed}`.",
        "",
        "## Scenario statements",
        "",
        *[f"- {item}" for item in result.flagship_input.assumptions],
    ]
    return "\n".join(lines) + "\n"


def write_flagship_artifacts(
    result: FlagshipWorldResult,
    output_dir: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Write one complete flagship run from canonical Representation sources."""
    output = write_world_artifacts(
        result.structural_result,
        output_dir,
        overwrite=overwrite,
    )
    manifest_path = output / "manifest.json"
    manifest_path.unlink()

    (output / "inputs" / "flagship-input.json").write_bytes(
        result.normalized_input_bytes
    )
    (output / "wells").mkdir(exist_ok=True)
    (output / "wells" / "flagship-well-trajectory.csv").write_bytes(
        result.trajectory_bytes
    )
    (output / "observations").mkdir(exist_ok=True)
    (output / "observations" / "well-pressure.csv").write_bytes(
        result.observation_bytes
    )
    _write_json(
        output / "observations" / "well-pressure.json",
        {
            "observation": result.observation.model_dump(mode="json"),
            "representation": next(
                item.model_dump(mode="json")
                for item in result.world.representations
                if item.ref == result.observation.representation
            ),
        },
    )
    write_representation_bundle(output, result.baseline_bundle)
    write_representation_bundle(output, result.perturbed_bundle)

    _write_json(output / "world.json", result.world.model_dump(mode="json"))
    _write_json(
        output / "world_summary.json",
        {
            "world_id": result.world.world_id,
            "entity_count": len(result.world.entities),
            "relation_count": len(result.world.relations),
            "state_ids": [item.state_id for item in result.world.states],
            "field_binding_count": len(result.world.field_bindings),
            "representation_count": len(result.world.representations),
            "observation_ids": [item.observation_id for item in result.world.observations],
        },
    )
    _write_json(output / "world_graph.json", _world_graph(result))
    _write_json(output / "state_lineage.json", _state_lineage(result))
    _write_json(
        output / "provenance.json",
        [item.model_dump(mode="json") for item in result.world.provenance],
    )
    _write_json(
        output / "flagship_execution.json",
        {
            "methods": [
                "illustrative_hydrostatic_pressure_v1",
                "linear_geothermal_gradient_v1",
                "analytic_pressure_perturbation_v1",
                result.flagship_input.observation.sampling_method,
            ],
            "seed_lineage": result.observation_seed_lineage,
            "state_lineage": [
                STRUCTURAL_STATE_ID,
                BASELINE_STATE_ID,
                PERTURBED_STATE_ID,
            ],
        },
    )
    (output / "assumptions.md").write_text(
        _assumptions_markdown(result),
        encoding="utf-8",
    )
    (output / "report.md").write_text(
        "# Flagship faulted reservoir World\n\n"
        "A bounded synthetic demonstration of persistent geological identity, "
        "immutable state change, and synthetic evidence.\n\n"
        "This is not a reservoir simulator, pressure-diffusion solution, or field interpretation.\n",
        encoding="utf-8",
    )
    if result.flagship_input.outputs.save_diagnostic_figure:
        save_flagship_diagnostic(result, output / "flagship_diagnostic.png")
    elif (output / "flagship_diagnostic.png").exists():
        (output / "flagship_diagnostic.png").unlink()

    artifact_paths = sorted(
        item for item in output.rglob("*") if item.is_file() and item.name != "manifest.json"
    )
    manifest = {
        "manifest_schema_version": "4.0",
        "software": {
            "name": "geoworld-open",
            "version": __version__,
            "python_version": platform.python_version(),
        },
        "workflow": "flagship-world",
        "flagship_input_sha256": hashlib.sha256(
            result.normalized_input_bytes
        ).hexdigest(),
        "world_id": result.world.world_id,
        "entity_ids": [item.entity_id for item in result.world.entities],
        "relation_ids": [item.relation_id for item in result.world.relations],
        "state_lineage": [STRUCTURAL_STATE_ID, BASELINE_STATE_ID, PERTURBED_STATE_ID],
        "methods": [
            "analytic_source_depth_v1",
            "explicit_layer_lookup_v1",
            "illustrative_hydrostatic_pressure_v1",
            "linear_geothermal_gradient_v1",
            "analytic_pressure_perturbation_v1",
            result.flagship_input.observation.sampling_method,
        ],
        "provenance_ids": [item.provenance_id for item in result.world.provenance],
        "field_binding_ids": [item.binding_id for item in result.world.field_bindings],
        "observation_id": result.observation.observation_id,
        "observation_representation": result.observation.representation.model_dump(
            mode="json"
        ),
        "representation_hashes": {
            f"{item.representation_id}@{item.version}": item.content_sha256
            for item in result.world.representations
        },
        "seed_lineage": result.observation_seed_lineage,
        "artifacts": [
            {
                "path": str(item.relative_to(output)),
                "bytes": item.stat().st_size,
                "sha256": file_sha256(item),
            }
            for item in artifact_paths
        ],
        "limitations": [
            "Synthetic educational benchmark, not field interpretation.",
            "Pressure change is analytic and is not reservoir simulation or diffusion.",
            "No permeability, mass conservation, fluid transport, or calibrated physics.",
        ],
    }
    _write_json(manifest_path, manifest)
    return output


def verify_flagship_artifacts(output_dir: str | Path) -> None:
    """Verify file checksums and every persisted Representation semantic hash."""
    output = Path(output_dir)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    for item in manifest["artifacts"]:
        path = output / item["path"]
        if not path.is_file() or file_sha256(path) != item["sha256"]:
            raise ValueError(f"flagship artifact checksum mismatch: {item['path']}")

    world = json.loads((output / "world.json").read_text(encoding="utf-8"))
    for representation in world["representations"]:
        artifact_path = output / artifact_relative_path(representation["artifact_uri"])
        if representation["kind"] == RepresentationKind.ARRAY.value:
            descriptor, dataset = load_representation_dataset(output, artifact_path)
            if descriptor["content_sha256"] != representation["content_sha256"]:
                raise ValueError(
                    f"Representation descriptor hash mismatch: {representation['representation_id']}"
                )
            actual = dataset_content_sha256(dataset)
        else:
            actual = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        if actual != representation["content_sha256"]:
            raise ValueError(
                f"Representation content hash mismatch: {representation['representation_id']}"
            )
