"""Minimal state-transition boundary; no domain physics is implemented here."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from geoworld_open.world.models import (
    FieldBinding,
    FrozenModel,
    Identifier,
    Provenance,
    Representation,
    SubjectKind,
    SubjectRef,
    WorldState,
)
from geoworld_open.world.registry import World


class TransitionResult(FrozenModel):
    """Append-only records produced by one deterministic transition capability."""

    state: WorldState
    field_bindings: tuple[FieldBinding, ...] = ()
    representations: tuple[Representation, ...] = ()
    provenance: tuple[Provenance, ...]


@runtime_checkable
class StateTransition(Protocol):
    """Layered Process-like contract outside the eight-concept kernel."""

    transition_id: Identifier

    def apply(self, world: World, input_state: WorldState) -> TransitionResult:
        """Return new records without mutating the World or input state."""
        ...


class TransitionExecution(FrozenModel):
    """Validated outcome of appending one transition to a World."""

    transition_id: Identifier
    input_state_id: Identifier
    output_state_id: Identifier
    world: World


def apply_transition(
    world: World,
    input_state_id: str,
    transition: StateTransition,
) -> TransitionExecution:
    """Execute and atomically validate one immutable state transition."""
    input_state = world.state(input_state_id)
    before = world.model_dump_json()
    result = transition.apply(world, input_state)

    if result.state.world_id != world.world_id:
        raise ValueError("transition output state belongs to another World")
    if result.state.parent_state_id != input_state.state_id:
        raise ValueError("transition output state must name the input state as parent")
    if result.state.state_id == input_state.state_id:
        raise ValueError("transition must produce a new WorldState ID")
    if not result.provenance:
        raise ValueError("transition must produce Provenance")
    if any(binding.world_state_id != result.state.state_id for binding in result.field_bindings):
        raise ValueError("transition FieldBindings must belong to the output state")

    provenance_inputs = {
        ref for record in result.provenance for ref in record.inputs
    }
    provenance_outputs = {
        ref for record in result.provenance for ref in record.outputs
    }
    input_ref = SubjectRef(
        kind=SubjectKind.WORLD_STATE,
        subject_id=input_state.state_id,
    )
    if input_ref not in provenance_inputs:
        raise ValueError("transition Provenance must identify the input WorldState")

    expected_outputs = {
        SubjectRef(kind=SubjectKind.WORLD_STATE, subject_id=result.state.state_id),
        *(
            SubjectRef(kind=SubjectKind.FIELD_BINDING, subject_id=binding.binding_id)
            for binding in result.field_bindings
        ),
        *(representation.ref for representation in result.representations),
    }
    missing_outputs = expected_outputs - provenance_outputs
    if missing_outputs:
        raise ValueError(
            "transition Provenance omits appended outputs: "
            + ", ".join(sorted(ref.subject_id for ref in missing_outputs))
        )

    output_records = [
        (
            SubjectRef(kind=SubjectKind.WORLD_STATE, subject_id=result.state.state_id),
            result.state,
        ),
        *(
            (
                SubjectRef(kind=SubjectKind.FIELD_BINDING, subject_id=binding.binding_id),
                binding,
            )
            for binding in result.field_bindings
        ),
        *((representation.ref, representation) for representation in result.representations),
    ]
    for output_ref, output_record in output_records:
        describing_ids = {
            record.provenance_id
            for record in result.provenance
            if output_ref in record.outputs
        }
        if not describing_ids.intersection(output_record.provenance_ids):
            raise ValueError(
                f"transition output {output_ref.subject_id!r} must cite Provenance "
                "that identifies it as an output"
            )

    updated = world.with_records(
        field_bindings=result.field_bindings,
        representations=result.representations,
        states=(result.state,),
        provenance=result.provenance,
    )
    if world.model_dump_json() != before:
        raise RuntimeError("transition mutated its input World")
    if tuple(entity.entity_id for entity in updated.entities) != tuple(
        entity.entity_id for entity in world.entities
    ):
        raise RuntimeError("transition changed persistent Entity identity")

    return TransitionExecution(
        transition_id=transition.transition_id,
        input_state_id=input_state.state_id,
        output_state_id=result.state.state_id,
        world=updated,
    )
