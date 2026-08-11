"""Gate 2 invariant tests for the universal world-kernel contracts."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import numpy as np
import pytest
import xarray as xr
from pydantic import ValidationError

from geoworld_open.world import (
    GROUND_TRUTH_SCOPE,
    FieldBinding,
    FieldDefinition,
    Missingness,
    Observation,
    ObservationStatus,
    PhysicalRank,
    Provenance,
    Representation,
    SubjectKind,
    SubjectRef,
    TemporalValue,
    TransitionResult,
    World,
    WorldOrigin,
    WorldState,
    WorldStateRole,
    XarrayBundle,
    apply_transition,
    create_xarray_bundle,
    dataset_content_sha256,
)
from tests.world_kernel_fixtures import KernelFixture, build_kernel_fixture


def _ref(kind: SubjectKind, subject_id: str, version: str | None = None) -> SubjectRef:
    return SubjectRef(
        kind=kind,
        subject_id=subject_id,
        representation_version=version,
    )


class DeterministicContractTransition:
    """Contract-test transition, deliberately not a scientific Process."""

    transition_id = "deterministic-contract-transition"

    def __init__(self, target_entity_id: str | None = None) -> None:
        self.target_entity_id = target_entity_id

    def apply(self, world: World, input_state: WorldState) -> TransitionResult:
        old_binding = next(
            binding
            for binding in world.field_bindings
            if binding.binding_id in input_state.field_binding_ids
        )
        old_representation = next(
            representation
            for representation in world.representations
            if representation.ref == old_binding.representation
        )
        state_id = f"{world.world_id}-state-t1"
        binding_id = f"{world.world_id}-binding-t1"
        representation_ref = _ref(
            SubjectKind.REPRESENTATION,
            old_representation.representation_id,
            "v2",
        )
        provenance_id = f"{world.world_id}-prov-transition"
        binding = FieldBinding(
            binding_id=binding_id,
            field_definition_id=old_binding.field_definition_id,
            subject=(
                _ref(SubjectKind.ENTITY, self.target_entity_id)
                if self.target_entity_id
                else old_binding.subject
            ),
            world_state_id=state_id,
            representation=representation_ref,
            support_id=old_binding.support_id,
            scale_label=old_binding.scale_label,
            provenance_ids=(provenance_id,),
        )
        representation = Representation(
            representation_id=old_representation.representation_id,
            version="v2",
            subjects=(_ref(SubjectKind.FIELD_BINDING, binding_id),),
            kind=old_representation.kind,
            artifact_uri=f"memory://{old_representation.representation_id}/v2",
            content_sha256=hashlib.sha256(
                f"{world.world_id}:{input_state.state_id}:v2".encode()
            ).hexdigest(),
            media_type=old_representation.media_type,
            support_id=old_representation.support_id,
            reference_frame_id=old_representation.reference_frame_id,
            dimensions=old_representation.dimensions,
            derived_from=(old_representation.ref,),
            provenance_ids=(provenance_id,),
        )
        state = WorldState(
            state_id=state_id,
            world_id=world.world_id,
            role=WorldStateRole.SIMULATED,
            parent_state_id=input_state.state_id,
            field_binding_ids=(binding_id,),
            representation_refs=(representation_ref,),
            provenance_ids=(provenance_id,),
        )
        provenance = Provenance(
            provenance_id=provenance_id,
            activity_type="contract_transition",
            method="deterministic metadata-only rebind for Gate 2",
            inputs=(
                _ref(SubjectKind.WORLD_STATE, input_state.state_id),
                old_representation.ref,
            ),
            outputs=(
                _ref(SubjectKind.WORLD_STATE, state_id),
                _ref(SubjectKind.FIELD_BINDING, binding_id),
                representation_ref,
            ),
            parent_provenance_ids=input_state.provenance_ids,
        )
        return TransitionResult(
            state=state,
            field_bindings=(binding,),
            representations=(representation,),
            provenance=(provenance,),
        )


class FixedResultTransition:
    transition_id = "fixed-result-transition"

    def __init__(self, result: TransitionResult) -> None:
        self.result = result

    def apply(self, world: World, input_state: WorldState) -> TransitionResult:
        return self.result


def _bundle_dataset(
    fixture: KernelFixture,
    dataset: xr.Dataset,
    *,
    definition_override: FieldDefinition | None = None,
) -> XarrayBundle:
    world = fixture.world
    binding = world.field_bindings[0]
    definition = definition_override or world.field_definitions[0]
    return create_xarray_bundle(
        dataset,
        world_id=world.world_id,
        state=world.states[0],
        support=world.supports[0],
        reference_frame=world.reference_frames[0],
        representation_id=binding.representation.subject_id,
        version=binding.representation.representation_version,
        variable_bindings={definition.canonical_name: binding},
        field_definitions=(definition,),
        provenance=world.provenance[1],
    )


@pytest.fixture(params=("reservoir", "heart", "robot"))
def kernel_fixture(request: pytest.FixtureRequest) -> KernelFixture:
    return build_kernel_fixture(str(request.param))


def test_cross_domain_fixtures_use_identical_kernel_classes(kernel_fixture: KernelFixture) -> None:
    world = kernel_fixture.world
    assert type(world) is World
    assert all(type(entity).__name__ == "Entity" for entity in world.entities)
    assert all(type(state) is WorldState for state in world.states)
    assert all(type(observation) is Observation for observation in world.observations)


def test_entity_identity_survives_representation_replacement() -> None:
    fixture = build_kernel_fixture("reservoir")
    world = fixture.world
    original = world.representations[0]
    replacement = Representation(
        representation_id=original.representation_id,
        version="v2",
        subjects=original.subjects,
        kind=original.kind,
        artifact_uri=f"memory://{original.representation_id}/v2",
        content_sha256="a" * 64,
        media_type=original.media_type,
        support_id=original.support_id,
        reference_frame_id=original.reference_frame_id,
        dimensions=original.dimensions,
        derived_from=(original.ref,),
        provenance_ids=original.provenance_ids,
    )
    updated = world.with_records(representations=(replacement,))
    assert updated.entities == world.entities
    assert updated.states[0].representation_refs == (original.ref,)


def test_representation_and_state_are_immutable_and_version_exact() -> None:
    fixture = build_kernel_fixture("reservoir")
    representation = fixture.world.representations[0]
    state = fixture.world.states[0]
    assert state.representation_refs == (representation.ref,)
    with pytest.raises(ValidationError, match="frozen"):
        representation.version = "v2"  # type: ignore[misc]
    with pytest.raises(ValidationError, match="frozen"):
        state.role = WorldStateRole.ASSERTED  # type: ignore[misc]


def test_one_field_definition_is_reused_across_states() -> None:
    fixture = build_kernel_fixture("reservoir")
    execution = apply_transition(
        fixture.world,
        fixture.state_id,
        DeterministicContractTransition(target_entity_id="well-w1"),
    )
    old_binding, new_binding = execution.world.field_bindings
    assert old_binding.field_definition_id == new_binding.field_definition_id
    assert old_binding.world_state_id != new_binding.world_state_id
    assert old_binding.subject != new_binding.subject
    assert old_binding.representation != new_binding.representation


def test_observation_is_evidence_not_world_state() -> None:
    observation = build_kernel_fixture("heart").world.observations[0]
    assert observation.status.value == "synthetic"
    assert not isinstance(observation, WorldState)
    with pytest.raises(ValidationError):
        WorldState.model_validate(observation.model_dump())


def test_unknown_subject_reference_is_rejected() -> None:
    fixture = build_kernel_fixture("robot")
    world = fixture.world
    bad_observation = world.observations[0].model_copy(
        update={"subjects": (_ref(SubjectKind.ENTITY, "missing-object"),)}
    )
    payload = world.model_dump(mode="python")
    payload["observations"] = (bad_observation,)
    with pytest.raises(ValidationError, match="unknown entity"):
        World.model_validate(payload)


def test_unknown_relation_entity_is_rejected() -> None:
    fixture = build_kernel_fixture("reservoir")
    world = fixture.world
    bad_relation = world.relations[0].model_copy(update={"target_entity_id": "missing"})
    payload = world.model_dump(mode="python")
    payload["relations"] = (bad_relation, *world.relations[1:])
    with pytest.raises(ValidationError, match="unknown target Entity"):
        World.model_validate(payload)


def test_xarray_adapter_round_trip_does_not_transfer_semantic_authority() -> None:
    fixture = build_kernel_fixture("reservoir")
    dataset = fixture.bundle.to_dataset()
    variable_name = next(iter(dataset.data_vars))
    definition = fixture.world.field_definitions[0]
    assert dataset.attrs["geoworld:world_id"] == fixture.world.world_id
    assert dataset[variable_name].attrs["units"] == definition.unit
    assert dataset[variable_name].attrs["geoworld:physical_rank"] == "scalar"
    assert dataset.coords["row"].attrs["units"] == "m"
    assert dataset[variable_name].ndim == 2
    dataset[variable_name].values[:] = -999.0
    assert (fixture.bundle.values_for_binding(fixture.field_binding_id) >= 0).all()


def test_multidimensional_array_does_not_define_physical_tensor_rank() -> None:
    fixture = build_kernel_fixture("heart")
    definition = fixture.world.field_definitions[0]
    dataset = fixture.bundle.to_dataset()
    assert definition.physical_rank == PhysicalRank.SCALAR
    assert next(iter(dataset.data_vars.values())).ndim == 2


def test_ground_truth_is_restricted_to_constructed_synthetic_worlds() -> None:
    fixture = build_kernel_fixture("reservoir")
    assert "known by construction" in GROUND_TRUTH_SCOPE
    payload = fixture.world.model_dump(mode="python")
    payload["origin"] = WorldOrigin.FIELD
    with pytest.raises(ValidationError, match="ground_truth.*synthetic World"):
        World.model_validate(payload)


def test_transition_is_deterministic_append_only_and_preserves_entities() -> None:
    fixture = build_kernel_fixture("reservoir")
    before = fixture.world.model_dump_json()
    first = apply_transition(
        fixture.world,
        fixture.state_id,
        DeterministicContractTransition(),
    )
    second_fixture = build_kernel_fixture("reservoir")
    second = apply_transition(
        second_fixture.world,
        second_fixture.state_id,
        DeterministicContractTransition(),
    )
    assert fixture.world.model_dump_json() == before
    assert first.world.model_dump_json() == second.world.model_dump_json()
    assert first.world.entities == fixture.world.entities
    assert first.world.state(first.output_state_id).parent_state_id == fixture.state_id
    assert len(first.world.states) == 2


def test_provenance_is_reproducible_and_reference_valid() -> None:
    first = build_kernel_fixture("robot").world
    second = build_kernel_fixture("robot").world
    first_digest = hashlib.sha256(first.model_dump_json().encode()).hexdigest()
    second_digest = hashlib.sha256(second.model_dump_json().encode()).hexdigest()
    assert first_digest == second_digest
    assert all("user" not in key for key, _ in first.metadata)
    assert {record.activity_type for record in first.provenance} == {
        "fixture_construction",
        "deterministic_fixture_values",
        "synthetic_observation",
    }


def test_representation_self_derivation_is_rejected() -> None:
    world = build_kernel_fixture("reservoir").world
    original = world.representations[0]
    version = original.model_copy(update={"version": "self-cycle"})
    version = version.model_copy(update={"derived_from": (version.ref,)})
    with pytest.raises(ValidationError, match="Representation lineage contains a cycle"):
        world.with_records(representations=(version,))


def test_representation_multi_node_derivation_cycle_is_rejected() -> None:
    world = build_kernel_fixture("reservoir").world
    original = world.representations[0]
    first_ref = _ref(SubjectKind.REPRESENTATION, original.representation_id, "cycle-a")
    second_ref = _ref(SubjectKind.REPRESENTATION, original.representation_id, "cycle-b")
    first = original.model_copy(update={"version": "cycle-a", "derived_from": (second_ref,)})
    second = original.model_copy(update={"version": "cycle-b", "derived_from": (first_ref,)})
    with pytest.raises(ValidationError, match="Representation lineage contains a cycle"):
        world.with_records(representations=(first, second))


def test_representation_longer_derivation_cycle_is_rejected() -> None:
    world = build_kernel_fixture("reservoir").world
    original = world.representations[0]
    refs = tuple(
        _ref(SubjectKind.REPRESENTATION, original.representation_id, version)
        for version in ("cycle-a", "cycle-b", "cycle-c")
    )
    records = tuple(
        original.model_copy(update={"version": ref.representation_version, "derived_from": (parent,)})
        for ref, parent in zip(refs, (*refs[1:], refs[0]))
    )
    with pytest.raises(ValidationError, match="Representation lineage contains a cycle"):
        world.with_records(representations=records)


@pytest.mark.parametrize(
    "records",
    [
        (
            Provenance(
                provenance_id="prov-cycle-a",
                activity_type="test",
                method="self cycle",
                parent_provenance_ids=("prov-cycle-a",),
            ),
        ),
        (
            Provenance(
                provenance_id="prov-cycle-a",
                activity_type="test",
                method="three-node cycle",
                parent_provenance_ids=("prov-cycle-b",),
            ),
            Provenance(
                provenance_id="prov-cycle-b",
                activity_type="test",
                method="three-node cycle",
                parent_provenance_ids=("prov-cycle-c",),
            ),
            Provenance(
                provenance_id="prov-cycle-c",
                activity_type="test",
                method="three-node cycle",
                parent_provenance_ids=("prov-cycle-a",),
            ),
        ),
        (
            Provenance(
                provenance_id="prov-cycle-a",
                activity_type="test",
                method="two-node cycle",
                parent_provenance_ids=("prov-cycle-b",),
            ),
            Provenance(
                provenance_id="prov-cycle-b",
                activity_type="test",
                method="two-node cycle",
                parent_provenance_ids=("prov-cycle-a",),
            ),
        ),
    ],
)
def test_provenance_cycles_are_rejected(records: tuple[Provenance, ...]) -> None:
    world = build_kernel_fixture("heart").world
    with pytest.raises(ValidationError, match="Provenance lineage contains a cycle"):
        world.with_records(provenance=records)


def test_provenance_shared_ancestry_remains_a_valid_dag() -> None:
    world = build_kernel_fixture("heart").world
    root = Provenance(provenance_id="shared-root", activity_type="test", method="root")
    left = Provenance(
        provenance_id="shared-left",
        activity_type="test",
        method="left",
        parent_provenance_ids=(root.provenance_id,),
    )
    right = Provenance(
        provenance_id="shared-right",
        activity_type="test",
        method="right",
        parent_provenance_ids=(root.provenance_id,),
    )
    joined = Provenance(
        provenance_id="shared-join",
        activity_type="test",
        method="join",
        parent_provenance_ids=(left.provenance_id, right.provenance_id),
    )
    updated = world.with_records(provenance=(root, left, right, joined))
    assert updated.provenance[-1] == joined


def test_transition_provenance_requires_input_state_and_preserves_original() -> None:
    fixture = build_kernel_fixture("reservoir")
    original = fixture.world.model_dump_json()
    result = DeterministicContractTransition().apply(
        fixture.world,
        fixture.world.state(fixture.state_id),
    )
    bad_provenance = result.provenance[0].model_copy(update={"inputs": ()})
    bad_result = result.model_copy(update={"provenance": (bad_provenance,)})
    with pytest.raises(ValueError, match="input WorldState"):
        apply_transition(fixture.world, fixture.state_id, FixedResultTransition(bad_result))
    assert fixture.world.model_dump_json() == original


def test_transition_provenance_requires_every_output_and_preserves_original() -> None:
    fixture = build_kernel_fixture("reservoir")
    original = fixture.world.model_dump_json()
    result = DeterministicContractTransition().apply(
        fixture.world,
        fixture.world.state(fixture.state_id),
    )
    omitted = _ref(SubjectKind.FIELD_BINDING, result.field_bindings[0].binding_id)
    outputs = tuple(ref for ref in result.provenance[0].outputs if ref != omitted)
    bad_provenance = result.provenance[0].model_copy(update={"outputs": outputs})
    bad_result = result.model_copy(update={"provenance": (bad_provenance,)})
    with pytest.raises(ValueError, match="omits appended outputs"):
        apply_transition(fixture.world, fixture.state_id, FixedResultTransition(bad_result))
    assert fixture.world.model_dump_json() == original


def test_transition_output_must_cite_the_provenance_that_describes_it() -> None:
    fixture = build_kernel_fixture("reservoir")
    result = DeterministicContractTransition().apply(
        fixture.world,
        fixture.world.state(fixture.state_id),
    )
    unrelated = Provenance(
        provenance_id="unrelated-transition-provenance",
        activity_type="test",
        method="does not describe the state output",
    )
    state = result.state.model_copy(update={"provenance_ids": (unrelated.provenance_id,)})
    bad_result = result.model_copy(
        update={"state": state, "provenance": (*result.provenance, unrelated)}
    )
    with pytest.raises(ValueError, match="must cite Provenance"):
        apply_transition(fixture.world, fixture.state_id, FixedResultTransition(bad_result))


@pytest.mark.parametrize("bad_value", (np.nan, np.inf, -np.inf))
def test_forbidden_missingness_rejects_nonfinite_values(bad_value: float) -> None:
    fixture = build_kernel_fixture("reservoir")
    name = fixture.world.field_definitions[0].canonical_name
    values = np.arange(6, dtype=np.float64).reshape(2, 3)
    values[0, 0] = bad_value
    dataset = xr.Dataset(
        {name: (("row", "column"), values)},
        coords={"row": [0, 1], "column": [0, 1, 2]},
    )
    with pytest.raises(ValueError, match="missing values|infinite values"):
        _bundle_dataset(fixture, dataset)


def test_allow_missingness_accepts_nan_but_rejects_infinity() -> None:
    fixture = build_kernel_fixture("reservoir")
    definition = fixture.world.field_definitions[0].model_copy(
        update={"missingness": Missingness.ALLOW}
    )
    values = np.arange(6, dtype=np.float64).reshape(2, 3)
    values[0, 0] = np.nan
    dataset = xr.Dataset(
        {definition.canonical_name: (("row", "column"), values)},
        coords={"row": [0, 1], "column": [0, 1, 2]},
    )
    assert _bundle_dataset(fixture, dataset, definition_override=definition)
    dataset[definition.canonical_name].values[0, 0] = np.inf
    with pytest.raises(ValueError, match="infinite values"):
        _bundle_dataset(fixture, dataset, definition_override=definition)


def test_mask_missingness_is_explicitly_outside_gate_2_adapter() -> None:
    fixture = build_kernel_fixture("reservoir")
    definition = fixture.world.field_definitions[0].model_copy(
        update={"missingness": Missingness.MASK}
    )
    dataset = xr.Dataset(
        {
            definition.canonical_name: (
                ("row", "column"),
                np.arange(6, dtype=np.float64).reshape(2, 3),
            )
        },
        coords={"row": [0, 1], "column": [0, 1, 2]},
    )
    with pytest.raises(ValueError, match="explicit mask representation"):
        _bundle_dataset(fixture, dataset, definition_override=definition)


def test_canonical_hash_rejects_non_string_keys_and_unsupported_objects() -> None:
    with pytest.raises(TypeError, match="keys must be strings"):
        dataset_content_sha256(xr.Dataset({"v": ("x", [1])}, attrs={1: "value"}))
    with pytest.raises(TypeError, match="unsupported metadata type"):
        dataset_content_sha256(
            xr.Dataset({"v": ("x", [1])}, attrs={"bad": object()})
        )


def test_canonical_hash_normalizes_endianness_but_preserves_precision() -> None:
    little = xr.Dataset({"v": ("x", np.array([1.5, 2.5], dtype="<f8"))})
    big = xr.Dataset({"v": ("x", np.array([1.5, 2.5], dtype=">f8"))})
    lower_precision = xr.Dataset({"v": ("x", np.array([1.5, 2.5], dtype="<f4"))})
    assert dataset_content_sha256(little) == dataset_content_sha256(big)
    assert dataset_content_sha256(little) != dataset_content_sha256(lower_precision)


def test_support_frame_dimension_order_mismatch_is_rejected() -> None:
    world = build_kernel_fixture("robot").world
    support = world.supports[0].model_copy(
        update={"dimension_names": ("column", "row"), "shape": (3, 2)}
    )
    payload = world.model_dump(mode="python")
    payload["supports"] = (support,)
    with pytest.raises(ValidationError, match="ordered subset"):
        World.model_validate(payload)


def test_representation_support_dimension_mismatch_is_rejected() -> None:
    world = build_kernel_fixture("robot").world
    bad = world.representations[0].model_copy(update={"dimensions": ("row",)})
    payload = world.model_dump(mode="python")
    payload["representations"] = (bad, *world.representations[1:])
    with pytest.raises(ValidationError, match="incompatible with its Support"):
        World.model_validate(payload)


def test_binding_and_representation_support_mismatch_is_rejected() -> None:
    world = build_kernel_fixture("robot").world
    bad = world.field_bindings[0].model_copy(update={"support_id": None})
    payload = world.model_dump(mode="python")
    payload["field_bindings"] = (bad,)
    with pytest.raises(ValidationError, match="different Supports"):
        World.model_validate(payload)


def test_state_must_include_each_binding_representation() -> None:
    world = build_kernel_fixture("robot").world
    bad = world.states[0].model_copy(update={"representation_refs": ()})
    payload = world.model_dump(mode="python")
    payload["states"] = (bad,)
    with pytest.raises(ValidationError, match="every FieldBinding Representation"):
        World.model_validate(payload)


def test_representation_and_support_frame_mismatch_is_rejected() -> None:
    world = build_kernel_fixture("robot").world
    extra_frame = world.reference_frames[0].model_copy(update={"frame_id": "other-frame"})
    bad = world.representations[0].model_copy(update={"reference_frame_id": extra_frame.frame_id})
    payload = world.model_dump(mode="python")
    payload["reference_frames"] = (*world.reference_frames, extra_frame)
    payload["representations"] = (bad, *world.representations[1:])
    with pytest.raises(ValidationError, match="reference different frames"):
        World.model_validate(payload)


def test_coordinate_direction_and_unit_conflicts_are_rejected() -> None:
    fixture = build_kernel_fixture("reservoir")
    name = fixture.world.field_definitions[0].canonical_name
    values = np.arange(6, dtype=np.float64).reshape(2, 3)
    descending = xr.Dataset(
        {name: (("row", "column"), values)},
        coords={"row": [1, 0], "column": [0, 1, 2]},
    )
    with pytest.raises(ValueError, match="strictly increasing"):
        _bundle_dataset(fixture, descending)

    wrong_unit = xr.Dataset(
        {name: (("row", "column"), values)},
        coords={"row": [0, 1], "column": [0, 1, 2]},
    )
    wrong_unit.coords["row"].attrs["units"] = "s"
    with pytest.raises(ValueError, match="unit conflicts"):
        _bundle_dataset(fixture, wrong_unit)


def test_temporal_value_rejects_naive_time_and_preserves_relative_time() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        TemporalValue(absolute_time=datetime(2026, 8, 11, 15, 0))
    relative = TemporalValue(relative_value=2.5, relative_unit="years")
    state = build_kernel_fixture("reservoir").world.states[0]
    updated = WorldState.model_validate(
        {**state.model_dump(mode="python"), "valid_from": relative}
    )
    assert updated.valid_from == relative
    assert updated.model_dump(mode="json")["valid_from"] == {
        "absolute_time": None,
        "relative_value": 2.5,
        "relative_unit": "years",
    }


@pytest.mark.parametrize(
    "payload",
    (
        {"relative_value": np.inf, "relative_unit": "days"},
        {"relative_value": 1.0},
        {"relative_unit": "days"},
        {
            "absolute_time": datetime(2026, 8, 11, tzinfo=timezone.utc),
            "relative_value": 1.0,
            "relative_unit": "days",
        },
    ),
)
def test_temporal_value_rejects_invalid_or_ambiguous_modes(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        TemporalValue.model_validate(payload)


def test_acquired_observation_requires_explicit_acquisition_time() -> None:
    observation = build_kernel_fixture("heart").world.observations[0]
    payload = observation.model_dump(mode="python")
    payload.update({"status": ObservationStatus.ACQUIRED, "acquisition_time": None})
    with pytest.raises(ValidationError, match="requires acquisition_time"):
        Observation.model_validate(payload)
    payload["acquisition_time"] = TemporalValue(
        absolute_time=datetime(2026, 8, 11, 20, 0, tzinfo=timezone.utc)
    )
    assert Observation.model_validate(payload).status == ObservationStatus.ACQUIRED


def test_physical_tensor_rank_is_independent_of_array_dimensionality() -> None:
    fixture = build_kernel_fixture("heart")
    base_definition = fixture.world.field_definitions[0]
    stress_definition = base_definition.model_copy(
        update={"physical_rank": PhysicalRank.TENSOR_2}
    )
    stress = xr.Dataset(
        {
            stress_definition.canonical_name: (
                ("row", "column", "i", "j"),
                np.zeros((2, 3, 2, 2), dtype=np.float64),
            )
        },
        coords={
            "row": [0, 1],
            "column": [0, 1, 2],
            "i": [0, 1],
            "j": [0, 1],
        },
    )
    bundle = _bundle_dataset(fixture, stress, definition_override=stress_definition)
    assert bundle.representation.dimensions == ("row", "column", "i", "j")
    assert stress_definition.physical_rank == PhysicalRank.TENSOR_2

    seismic = xr.DataArray(
        np.zeros((2, 3, 4, 5)),
        dims=("vintage", "angle", "time", "x"),
    )
    seismic_definition = base_definition.model_copy(
        update={"physical_rank": PhysicalRank.NOT_APPLICABLE}
    )
    assert seismic.ndim == 4
    assert seismic_definition.physical_rank != PhysicalRank.TENSOR_2
