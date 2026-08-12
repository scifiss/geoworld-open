import hashlib
from pathlib import Path

import numpy as np

from geoworld_open.domains.geoscience.structural import run_structural_world
from geoworld_open.engine import SeedManager
from geoworld_open.specs import GeoSpec, load_geospec
from geoworld_open.world import SubjectKind, ValueKind


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "scenarios" / "structural_multifault.yaml"

PHASE2_ARRAY_HASHES = {
    "source_depth_m": "ae53e63b6eb9e609e3805a4df343cab14bae9abfc0c3fa2bbebcdfbe10762319",
    "structural_displacement_m": "6bf421c5f4a2f078e75b14a98fbe3d612d9b42ab49121686e334abc959a3c34c",
    "fold_displacement_m": "9e1b866c4364951db8d6e5de1f6710c89976f763ea04e7f4c91a5e9b66ce3e4e",
    "fault_displacement_m": "c8b43716416e4e59954c911cfb1687289a9cc5a2142757a94f21c4fdc34d7eed",
    "fault_selection": "31c3ff2fcf7ffe3589d22544e60aaeb7c5d740d31832bdf5883be7a3cec0c885",
    "boundary_clipped_mask": "ad539bb65c7455ec9e75e92b585cf7b7a79889f6ffc789a8da604b6d010242af",
    "layer_index": "40393e27be5df3fa61c8cd576ce10ae5ab27c33983231ea0898f4cc584a3e62a",
    "facies": "d4f2b915d3290491c5d03b183333525322ff157b9b13f46c8ecdaaaf744e5ae9",
    "porosity": "3c35c1c1cd9929baaaf843c56fdda7b2444ec89c302d268ef865db85e725e1a3",
    "reservoir_selection": "cec03a6a2e6e16de1fc9a87ce60b436f1cbf3c6dc4ea2d28b9920e80790290f4",
}


def _result():
    return run_structural_world(load_geospec(EXAMPLE))


def test_formations_and_faults_keep_identity_across_transition() -> None:
    result = _result()
    initial_ids = tuple(item.entity_id for item in result.initial_world.entities)
    final_ids = tuple(item.entity_id for item in result.world.entities)
    assert initial_ids == final_ids
    assert {item.entity_id for item in result.world.entities if item.entity_type == "geoscience:formation"} == {
        "formation:upper_shale", "formation:upper_sand", "formation:middle_shale", "formation:lower_sand"
    }
    assert {item.entity_id for item in result.world.entities if item.entity_type == "geoscience:fault"} == {
        "fault:east_normal_fault", "fault:west_reverse_fault"
    }
    assert result.dataset.coords["fault"].values.tolist() == [
        "fault:east_normal_fault", "fault:west_reverse_fault"
    ]
    assert float(result.dataset["fault_displacement_m"].min()) < 0.0
    assert float(result.dataset["fault_displacement_m"].max()) > 0.0
    assert result.numerical.diagnostics["structural_geometry"]["fault_count"] == 2


def test_changed_numerical_geometry_does_not_replace_geological_entities() -> None:
    spec = load_geospec(EXAMPLE)
    payload = spec.model_dump(mode="python")
    payload["structures"][1]["throw_m"] = 55.0
    changed = run_structural_world(GeoSpec.model_validate(payload))
    original = run_structural_world(spec)
    assert tuple(item.entity_id for item in original.world.entities) == tuple(
        item.entity_id for item in changed.world.entities
    )
    assert (
        original.geometry_bundle.representation.content_sha256
        != changed.geometry_bundle.representation.content_sha256
    )


def test_fields_are_state_support_representation_and_provenance_bound() -> None:
    result = _result()
    final = result.world.state(result.final_state_id)
    definitions = {item.field_id: item for item in result.world.field_definitions}
    bindings = {item.binding_id: item for item in result.world.field_bindings}
    assert definitions["field:facies"].value_kind == ValueKind.CATEGORICAL
    assert definitions["field:porosity"].value_kind == ValueKind.CONTINUOUS
    for name in ("facies", "porosity", "structural_displacement_m", "reservoir_selection"):
        binding = bindings[f"binding:{name}:structural-final"]
        assert binding.world_state_id == final.state_id
        assert binding.support_id == "support:structural-grid"
        assert binding.subject.kind == SubjectKind.SUPPORT
        assert binding.representation in final.representation_refs
        assert binding.provenance_ids


def test_transition_is_immutable_and_provenance_covers_every_output() -> None:
    result = _result()
    assert len(result.initial_world.states) == 1
    assert not result.initial_world.field_bindings
    assert not result.initial_world.representations
    assert len(result.world.states) == 2
    assert result.world.state(result.final_state_id).parent_state_id == result.initial_state_id
    provenance_outputs = {ref for item in result.world.provenance for ref in item.outputs}
    for binding in result.world.field_bindings:
        assert any(ref.subject_id == binding.binding_id for ref in provenance_outputs)
    for representation in result.world.representations:
        assert representation.ref in provenance_outputs
    transition_records = [
        item for item in result.world.provenance if item.activity_type == "world:state_transition"
    ]
    assert len(transition_records) == 1
    assert any(ref.subject_id == result.initial_state_id for ref in transition_records[0].inputs)
    assert any(ref.subject_id == result.final_state_id for ref in transition_records[0].outputs)


def test_same_spec_and_seed_have_identical_semantic_and_numerical_hashes() -> None:
    first = _result()
    second = _result()
    assert first.world.model_dump_json() == second.world.model_dump_json()
    assert [item.content_sha256 for item in first.world.representations] == [
        item.content_sha256 for item in second.world.representations
    ]
    for name in first.dataset.data_vars:
        np.testing.assert_array_equal(first.dataset[name], second.dataset[name])


def test_gate3_arrays_match_frozen_phase2_reference_hashes() -> None:
    dataset = _result().dataset
    for name, expected in PHASE2_ARRAY_HASHES.items():
        values = np.ascontiguousarray(dataset[name].values)
        assert hashlib.sha256(values.tobytes()).hexdigest() == expected


def test_seed_manager_is_order_independent_reproducible_and_seed_sensitive() -> None:
    manager = SeedManager(42)
    first_a = manager.generator("a").normal(size=8)
    first_b = manager.generator("b").normal(size=8)
    second_b = manager.generator("b").normal(size=8)
    second_a = manager.generator("a").normal(size=8)
    np.testing.assert_array_equal(first_a, second_a)
    np.testing.assert_array_equal(first_b, second_b)
    assert not np.array_equal(first_a, SeedManager(43).generator("a").normal(size=8))
