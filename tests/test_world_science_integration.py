import hashlib
import json
from pathlib import Path

import numpy as np

from geoworld_open.domains.geoscience.structural import run_structural_world
from geoworld_open.engine import SeedManager
from geoworld_open.specs import GeoSpec, load_geospec
from geoworld_open.world import SubjectKind, ValueKind


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "scenarios" / "structural_multifault.yaml"

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
    assert [item.representation_id for item in result.initial_world.representations] == [
        "representation:structural-input"
    ]
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
    fixture = json.loads(
        (ROOT / "tests" / "fixtures" / "phase2_structural_regression.json").read_text(
            encoding="utf-8"
        )
    )
    assert fixture["source_commit"] == "10b43f00abd456ccbb85653898250bfdfd748fcb"
    for name, expected in fixture["array_sha256"].items():
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
