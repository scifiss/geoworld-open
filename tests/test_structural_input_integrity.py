import hashlib
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from geoworld_open.domains.geoscience.structural import (
    bootstrap_structural_world,
    canonical_structural_input_bytes,
    compile_structural_input,
    run_structural_world,
    structural_input_sha256,
)
from geoworld_open.domains.geoscience.structural.capabilities import structural_capabilities
from geoworld_open.domains.geoscience.structural.integration import (
    INITIAL_STATE_ID,
    StructuralTransition,
)
from geoworld_open.engine import compile_plan
from geoworld_open.specs import GeoSpec, load_geospec
from geoworld_open.world import SubjectKind, apply_transition
from geoworld_open.world_artifacts import (
    file_sha256,
    verify_world_artifact_checksums,
    write_world_artifacts,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "scenarios" / "structural_multifault.yaml"


def _modified_spec(change: str) -> GeoSpec:
    spec = load_geospec(EXAMPLE)
    payload = spec.model_dump(mode="python")
    if change == "porosity":
        payload["layers"][1]["porosity_fraction"] = 0.31
    elif change == "reservoir_role":
        payload["layers"][1]["is_reservoir"] = False
    elif change == "fault_throw":
        payload["structures"][1]["throw_m"] = 70.0
    elif change == "fault_dip":
        payload["structures"][1]["dip_deg"] = 50.0
    elif change == "facies_code":
        payload["facies"][1]["code"] = 7
    elif change == "layer_thickness":
        payload["layers"][0]["thickness_m"] += 10.0
        payload["layers"][1]["thickness_m"] -= 10.0
    else:
        raise AssertionError(change)
    return GeoSpec.model_validate(payload)


@pytest.mark.parametrize(
    "change",
    (
        "porosity",
        "reservoir_role",
        "fault_throw",
        "fault_dip",
        "facies_code",
        "layer_thickness",
    ),
)
def test_scientific_parameter_changes_change_canonical_input_hash(change: str) -> None:
    original = compile_structural_input(load_geospec(EXAMPLE))
    changed = compile_structural_input(_modified_spec(change))
    assert structural_input_sha256(original) != structural_input_sha256(changed)


def test_equivalent_input_has_stable_canonical_bytes_and_hash() -> None:
    first = compile_structural_input(load_geospec(EXAMPLE))
    second = compile_structural_input(load_geospec(EXAMPLE))
    assert canonical_structural_input_bytes(first) == canonical_structural_input_bytes(second)
    assert structural_input_sha256(first) == structural_input_sha256(second)


@pytest.mark.parametrize(
    "change",
    ("porosity", "reservoir_role", "fault_throw", "facies_code"),
)
def test_world_rejects_mismatched_compiled_input_before_execution(change: str) -> None:
    original_input = compile_structural_input(load_geospec(EXAMPLE))
    world = bootstrap_structural_world(original_input)
    before = world.model_dump_json()
    transition = StructuralTransition(
        compile_structural_input(_modified_spec(change)),
        compile_plan(structural_capabilities()),
    )
    with pytest.raises(ValueError, match="does not match"):
        apply_transition(world, INITIAL_STATE_ID, transition)
    assert transition.numerical is None
    assert transition.geometry_bundle is None
    assert transition.stratigraphy_bundle is None
    assert world.model_dump_json() == before
    assert len(world.states) == 1
    assert not world.field_bindings
    assert len(world.representations) == 1


def test_exact_input_representation_and_typed_output_lineage() -> None:
    result = run_structural_world(load_geospec(EXAMPLE))
    input_representation = next(
        item
        for item in result.world.representations
        if item.representation_id == "representation:structural-input"
    )
    assert input_representation.version == "v1"
    assert input_representation.artifact_uri == "artifact://inputs/structural-input.json"
    assert input_representation.content_sha256 == hashlib.sha256(
        result.normalized_input_bytes
    ).hexdigest()
    assert input_representation.ref in result.initial_world.state(
        result.initial_state_id
    ).representation_refs

    provenance = {item.provenance_id: item for item in result.world.provenance}
    transition = provenance["provenance:structural-transition"]
    assert input_representation.ref in transition.inputs
    assert any(item.kind == SubjectKind.ENTITY for item in transition.inputs)
    assert {
        item.ref
        for item in result.world.representations
        if item.representation_id != "representation:structural-input"
    }.issubset(set(transition.outputs))
    assert {
        (SubjectKind.FIELD_BINDING, item.binding_id)
        for item in result.world.field_bindings
    }.issubset({(item.kind, item.subject_id) for item in transition.outputs})
    for name in ("porosity", "fault_displacement_m"):
        binding = next(
            item
            for item in result.world.field_bindings
            if item.binding_id == f"binding:{name}:structural-final"
        )
        derivation = provenance[binding.provenance_ids[0]]
        assert input_representation.ref in derivation.inputs
        assert any(
            output.kind == SubjectKind.FIELD_BINDING
            and output.subject_id == binding.binding_id
            for output in derivation.outputs
        )


def test_mutating_returned_dataset_cannot_change_exported_canonical_content(tmp_path) -> None:
    result = run_structural_world(load_geospec(EXAMPLE))
    expected = result.stratigraphy_bundle.to_dataset()["porosity"].values.copy()
    mutable_copy = result.dataset
    mutable_copy["porosity"].values[:] = 0.0
    output = write_world_artifacts(result, tmp_path / "run")
    np.testing.assert_array_equal(
        np.load(output / "arrays" / "porosity.npy", allow_pickle=False),
        expected,
    )
    verify_world_artifact_checksums(output)


def test_exporter_rejects_bundle_content_that_disagrees_with_representation(tmp_path) -> None:
    result = run_structural_world(load_geospec(EXAMPLE))

    class ForgedBundle:
        representation = result.stratigraphy_bundle.representation
        variable_bindings = result.stratigraphy_bundle.variable_bindings

        def to_dataset(self):
            dataset = result.stratigraphy_bundle.to_dataset()
            dataset["porosity"].values[:] = 0.0
            return dataset

    forged = replace(result, stratigraphy_bundle=ForgedBundle())
    with pytest.raises(ValueError, match="does not match"):
        write_world_artifacts(forged, tmp_path / "forged")


def test_semantic_content_verification_is_independent_of_file_checksum(tmp_path) -> None:
    result = run_structural_world(load_geospec(EXAMPLE))
    output = write_world_artifacts(result, tmp_path / "run")
    porosity_path = (
        output
        / "representations"
        / "stratigraphic-fields"
        / "variables"
        / "porosity.npy"
    )
    values = np.load(porosity_path, allow_pickle=False)
    np.save(porosity_path, np.zeros_like(values), allow_pickle=False)

    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    relative = str(porosity_path.relative_to(output))
    artifact = next(item for item in manifest["artifacts"] if item["path"] == relative)
    artifact["sha256"] = file_sha256(porosity_path)
    artifact["bytes"] = porosity_path.stat().st_size
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    with pytest.raises(ValueError, match="Representation content hash mismatch"):
        verify_world_artifact_checksums(output)


def test_output_options_are_honored_without_removing_canonical_representations(tmp_path) -> None:
    payload = load_geospec(EXAMPLE).model_dump(mode="python")
    payload["outputs"]["save_arrays"] = False
    payload["outputs"]["save_dataset_metadata"] = False
    payload["outputs"]["save_diagnostic_figure"] = False
    result = run_structural_world(GeoSpec.model_validate(payload))
    output = write_world_artifacts(result, tmp_path / "minimal")
    assert not (output / "arrays").exists()
    assert not (output / "coordinates").exists()
    assert not (output / "dataset_metadata.json").exists()
    assert not (output / "structure_diagnostic.png").exists()
    assert (output / "representations" / "structural-geometry" / "metadata.json").is_file()
    assert (output / "representations" / "stratigraphic-fields" / "metadata.json").is_file()
    verify_world_artifact_checksums(output)


def test_persisted_world_contains_no_memory_representation_uri(tmp_path) -> None:
    output = write_world_artifacts(
        run_structural_world(load_geospec(EXAMPLE)),
        tmp_path / "run",
    )
    world = json.loads((output / "world.json").read_text(encoding="utf-8"))
    assert all(
        item["artifact_uri"].startswith("artifact://")
        and not item["artifact_uri"].startswith("memory://")
        for item in world["representations"]
    )
