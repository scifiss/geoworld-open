"""Validated World registry and immutable state history."""

from __future__ import annotations

from enum import Enum
from typing import Callable, Iterable, TypeVar

from pydantic import Field as PydanticField, model_validator

from geoworld_open.world.models import (
    Entity,
    FieldBinding,
    FieldDefinition,
    FrozenModel,
    Identifier,
    NonEmptyStr,
    Observation,
    Provenance,
    ReferenceFrame,
    Relation,
    Representation,
    SubjectKind,
    SubjectRef,
    Support,
    WorldState,
    WorldStateRole,
)


class WorldOrigin(str, Enum):
    FIELD = "field"
    SYNTHETIC = "synthetic"


RecordT = TypeVar("RecordT")


def _index_unique(
    records: Iterable[RecordT],
    key: Callable[[RecordT], object],
    label: str,
) -> dict[object, RecordT]:
    result: dict[object, RecordT] = {}
    for record in records:
        record_key = key(record)
        if record_key in result:
            raise ValueError(f"duplicate {label}: {record_key!r}")
        result[record_key] = record
    return result


class World(FrozenModel):
    """Persistent semantic scope; numerical data remain in Representations."""

    world_id: Identifier
    label: NonEmptyStr
    origin: WorldOrigin
    entities: tuple[Entity, ...] = ()
    relations: tuple[Relation, ...] = ()
    field_definitions: tuple[FieldDefinition, ...] = ()
    field_bindings: tuple[FieldBinding, ...] = ()
    representations: tuple[Representation, ...] = ()
    states: tuple[WorldState, ...] = ()
    observations: tuple[Observation, ...] = ()
    provenance: tuple[Provenance, ...] = ()
    reference_frames: tuple[ReferenceFrame, ...] = ()
    supports: tuple[Support, ...] = ()
    metadata: tuple[tuple[Identifier, str], ...] = PydanticField(default=())

    @model_validator(mode="after")
    def validate_registry(self) -> "World":
        entities = _index_unique(self.entities, lambda item: item.entity_id, "entity ID")
        relations = _index_unique(self.relations, lambda item: item.relation_id, "relation ID")
        definitions = _index_unique(
            self.field_definitions,
            lambda item: item.field_id,
            "FieldDefinition ID",
        )
        bindings = _index_unique(
            self.field_bindings,
            lambda item: item.binding_id,
            "FieldBinding ID",
        )
        representations = _index_unique(
            self.representations,
            lambda item: (item.representation_id, item.version),
            "Representation version",
        )
        states = _index_unique(self.states, lambda item: item.state_id, "WorldState ID")
        observations = _index_unique(
            self.observations,
            lambda item: item.observation_id,
            "Observation ID",
        )
        provenance = _index_unique(
            self.provenance,
            lambda item: item.provenance_id,
            "Provenance ID",
        )
        frames = _index_unique(
            self.reference_frames,
            lambda item: item.frame_id,
            "ReferenceFrame ID",
        )
        supports = _index_unique(self.supports, lambda item: item.support_id, "Support ID")

        metadata_keys = [key for key, _ in self.metadata]
        if len(metadata_keys) != len(set(metadata_keys)):
            raise ValueError("World metadata keys must be unique")

        def resolve(ref: SubjectRef, owner: str) -> None:
            registries: dict[SubjectKind, dict[object, object]] = {
                SubjectKind.ENTITY: entities,
                SubjectKind.RELATION: relations,
                SubjectKind.FIELD_DEFINITION: definitions,
                SubjectKind.FIELD_BINDING: bindings,
                SubjectKind.WORLD_STATE: states,
                SubjectKind.SUPPORT: supports,
                SubjectKind.OBSERVATION: observations,
            }
            if ref.kind == SubjectKind.REPRESENTATION:
                key = (ref.subject_id, ref.representation_version)
                if key not in representations:
                    raise ValueError(f"{owner} references unknown Representation version {key!r}")
                return
            registry = registries[ref.kind]
            if ref.subject_id not in registry:
                raise ValueError(
                    f"{owner} references unknown {ref.kind.value} {ref.subject_id!r}"
                )

        def require_provenance(ids: tuple[str, ...], owner: str) -> None:
            for provenance_id in ids:
                if provenance_id not in provenance:
                    raise ValueError(
                        f"{owner} references unknown Provenance {provenance_id!r}"
                    )

        for entity in self.entities:
            require_provenance(entity.provenance_ids, f"Entity {entity.entity_id!r}")

        for relation in self.relations:
            if relation.source_entity_id not in entities:
                raise ValueError(
                    f"Relation {relation.relation_id!r} references unknown source Entity"
                )
            if relation.target_entity_id not in entities:
                raise ValueError(
                    f"Relation {relation.relation_id!r} references unknown target Entity"
                )
            for state_id in (relation.valid_from_state_id, relation.valid_to_state_id):
                if state_id is not None and state_id not in states:
                    raise ValueError(
                        f"Relation {relation.relation_id!r} references unknown WorldState {state_id!r}"
                    )
            require_provenance(relation.provenance_ids, f"Relation {relation.relation_id!r}")

        for frame in self.reference_frames:
            require_provenance(frame.provenance_ids, f"ReferenceFrame {frame.frame_id!r}")

        for support in self.supports:
            if support.reference_frame_id and support.reference_frame_id not in frames:
                raise ValueError(
                    f"Support {support.support_id!r} references unknown ReferenceFrame"
                )
            require_provenance(support.provenance_ids, f"Support {support.support_id!r}")

        for definition in self.field_definitions:
            require_provenance(
                definition.provenance_ids,
                f"FieldDefinition {definition.field_id!r}",
            )

        for representation in self.representations:
            for subject in representation.subjects:
                resolve(
                    subject,
                    f"Representation {(representation.representation_id, representation.version)!r}",
                )
            if representation.support_id and representation.support_id not in supports:
                raise ValueError(
                    f"Representation {representation.representation_id!r} references unknown Support"
                )
            if (
                representation.reference_frame_id
                and representation.reference_frame_id not in frames
            ):
                raise ValueError(
                    f"Representation {representation.representation_id!r} references unknown ReferenceFrame"
                )
            for parent in representation.derived_from:
                resolve(parent, f"Representation {representation.representation_id!r}")
            require_provenance(
                representation.provenance_ids,
                f"Representation {representation.representation_id!r}",
            )

        for binding in self.field_bindings:
            if binding.field_definition_id not in definitions:
                raise ValueError(
                    f"FieldBinding {binding.binding_id!r} references unknown FieldDefinition"
                )
            if binding.world_state_id not in states:
                raise ValueError(
                    f"FieldBinding {binding.binding_id!r} references unknown WorldState"
                )
            if binding.support_id and binding.support_id not in supports:
                raise ValueError(
                    f"FieldBinding {binding.binding_id!r} references unknown Support"
                )
            resolve(binding.subject, f"FieldBinding {binding.binding_id!r}")
            resolve(binding.representation, f"FieldBinding {binding.binding_id!r}")
            representation = representations[
                (binding.representation.subject_id, binding.representation.representation_version)
            ]
            expected_subject = SubjectRef(
                kind=SubjectKind.FIELD_BINDING,
                subject_id=binding.binding_id,
            )
            if expected_subject not in representation.subjects:
                raise ValueError(
                    f"FieldBinding {binding.binding_id!r} Representation subject must reference the binding"
                )
            definition = definitions[binding.field_definition_id]
            if binding.support_id:
                support_kind = supports[binding.support_id].support_kind
                if (
                    definition.admissible_support_kinds
                    and support_kind not in definition.admissible_support_kinds
                ):
                    raise ValueError(
                        f"FieldBinding {binding.binding_id!r} uses an inadmissible Support kind"
                    )
            require_provenance(binding.provenance_ids, f"FieldBinding {binding.binding_id!r}")

        for state in self.states:
            if state.world_id != self.world_id:
                raise ValueError(f"WorldState {state.state_id!r} belongs to another World")
            if state.role == WorldStateRole.GROUND_TRUTH and self.origin != WorldOrigin.SYNTHETIC:
                raise ValueError("ground_truth WorldState is allowed only in a synthetic World")
            if state.parent_state_id and state.parent_state_id not in states:
                raise ValueError(
                    f"WorldState {state.state_id!r} references unknown parent WorldState"
                )
            for binding_id in state.field_binding_ids:
                if binding_id not in bindings:
                    raise ValueError(
                        f"WorldState {state.state_id!r} references unknown FieldBinding {binding_id!r}"
                    )
                if bindings[binding_id].world_state_id != state.state_id:
                    raise ValueError(
                        f"FieldBinding {binding_id!r} is assigned to a different WorldState"
                    )
            for representation_ref in state.representation_refs:
                resolve(representation_ref, f"WorldState {state.state_id!r}")
            require_provenance(state.provenance_ids, f"WorldState {state.state_id!r}")

        self._validate_state_ancestry(states)

        for observation in self.observations:
            if observation.world_id != self.world_id:
                raise ValueError(f"Observation {observation.observation_id!r} belongs to another World")
            for subject in observation.subjects:
                resolve(subject, f"Observation {observation.observation_id!r}")
            resolve(observation.representation, f"Observation {observation.observation_id!r}")
            evidence = representations[
                (
                    observation.representation.subject_id,
                    observation.representation.representation_version,
                )
            ]
            expected_subject = SubjectRef(
                kind=SubjectKind.OBSERVATION,
                subject_id=observation.observation_id,
            )
            if expected_subject not in evidence.subjects:
                raise ValueError(
                    f"Observation {observation.observation_id!r} Representation must depict the observation"
                )
            require_provenance(
                observation.provenance_ids,
                f"Observation {observation.observation_id!r}",
            )

        for record in self.provenance:
            for ref in (*record.inputs, *record.outputs):
                resolve(ref, f"Provenance {record.provenance_id!r}")
            for parent_id in record.parent_provenance_ids:
                if parent_id not in provenance:
                    raise ValueError(
                        f"Provenance {record.provenance_id!r} references unknown parent"
                    )

        return self

    @staticmethod
    def _validate_state_ancestry(states: dict[object, WorldState]) -> None:
        for state in states.values():
            visited: set[str] = set()
            current: WorldState | None = state
            while current and current.parent_state_id:
                if current.state_id in visited:
                    raise ValueError("WorldState lineage contains a cycle")
                visited.add(current.state_id)
                current = states[current.parent_state_id]

    def with_records(
        self,
        *,
        field_bindings: tuple[FieldBinding, ...] = (),
        representations: tuple[Representation, ...] = (),
        states: tuple[WorldState, ...] = (),
        observations: tuple[Observation, ...] = (),
        provenance: tuple[Provenance, ...] = (),
    ) -> "World":
        """Return a fully revalidated World with append-only records."""
        payload = self.model_dump(mode="python")
        payload["field_bindings"] = self.field_bindings + field_bindings
        payload["representations"] = self.representations + representations
        payload["states"] = self.states + states
        payload["observations"] = self.observations + observations
        payload["provenance"] = self.provenance + provenance
        return World.model_validate(payload)

    def state(self, state_id: str) -> WorldState:
        """Return one state by stable ID."""
        for state in self.states:
            if state.state_id == state_id:
                return state
        raise KeyError(state_id)
