"""Gate 2 invariant tests for the universal world-kernel contracts."""

from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from geoworld_open.world import (
    GROUND_TRUTH_SCOPE,
    FieldBinding,
    Observation,
    PhysicalRank,
    Provenance,
    Representation,
    SubjectKind,
    SubjectRef,
    TransitionResult,
    World,
    WorldOrigin,
    WorldState,
    WorldStateRole,
    apply_transition,
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
