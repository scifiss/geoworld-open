"""Minimal state-transition boundary; no domain physics is implemented here."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from geoworld_open.world.models import (
    FieldBinding,
    FrozenModel,
    Identifier,
    Provenance,
    Representation,
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
