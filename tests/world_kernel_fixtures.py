"""Cross-domain semantic fixtures for the universal world kernel."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
import xarray as xr

from geoworld_open.world import (
    Directionality,
    Entity,
    FieldBinding,
    FieldDefinition,
    FrameScope,
    Observation,
    ObservationStatus,
    PhysicalRank,
    PositiveDirection,
    Provenance,
    ReferenceFrame,
    Relation,
    Representation,
    RepresentationKind,
    SubjectKind,
    SubjectRef,
    Support,
    SupportKind,
    ValueKind,
    World,
    WorldOrigin,
    WorldState,
    WorldStateRole,
    XarrayBundle,
    create_xarray_bundle,
)


@dataclass(frozen=True)
class KernelFixture:
    domain: str
    world: World
    bundle: XarrayBundle
    primary_entity_id: str
    field_definition_id: str
    field_binding_id: str
    state_id: str
    support_id: str


def _ref(kind: SubjectKind, subject_id: str, version: str | None = None) -> SubjectRef:
    return SubjectRef(
        kind=kind,
        subject_id=subject_id,
        representation_version=version,
    )


def build_kernel_fixture(domain: str) -> KernelFixture:
    if domain == "reservoir":
        entity_specs = (
            ("formation-a", "Formation"),
            ("fault-f1", "Fault"),
            ("well-w1", "Well"),
            ("brine", "FluidMaterial"),
            ("reservoir-r1", "ReservoirRegion"),
        )
        relation_specs = (
            ("rel-fault", "fault-f1", "INTERSECTS", "formation-a"),
            ("rel-well", "well-w1", "PENETRATES", "formation-a"),
            ("rel-region", "reservoir-r1", "PART_OF", "formation-a"),
        )
        primary_entity_id = "formation-a"
        field_name, unit = "pressure", "Pa"
        observation_type = "PressureGauge"
    elif domain == "heart":
        entity_specs = (("heart", "Heart"), ("chamber", "Chamber"))
        relation_specs = (("rel-chamber", "chamber", "PART_OF", "heart"),)
        primary_entity_id = "chamber"
        field_name, unit = "pressure", "Pa"
        observation_type = "PressureMeasurement"
    elif domain == "robot":
        entity_specs = (
            ("robot", "Robot"),
            ("gripper", "Gripper"),
            ("object", "Object"),
        )
        relation_specs = (("rel-gripper", "gripper", "PART_OF", "robot"),)
        primary_entity_id = "object"
        field_name, unit = "pose_x", "m"
        observation_type = "CameraFrame"
    else:
        raise ValueError(domain)

    prefix = f"{domain}-"
    seed_provenance_id = prefix + "prov-seed"
    data_provenance_id = prefix + "prov-data"
    observation_provenance_id = prefix + "prov-observation"
    frame_id = prefix + "frame"
    support_id = prefix + "support"
    field_definition_id = prefix + "field"
    field_binding_id = prefix + "binding-t0"
    state_id = prefix + "state-t0"
    representation_id = prefix + "field-bundle"
    observation_id = prefix + "observation"
    observation_representation_id = prefix + "observation-data"

    entities = tuple(
        Entity(
            entity_id=entity_id,
            entity_type=entity_type,
            label=entity_id.replace("-", " ").title(),
            provenance_ids=(seed_provenance_id,),
        )
        for entity_id, entity_type in entity_specs
    )
    relations = tuple(
        Relation(
            relation_id=relation_id,
            source_entity_id=source,
            relation_type=relation_type,
            target_entity_id=target,
            directionality=Directionality.DIRECTED,
            provenance_ids=(seed_provenance_id,),
        )
        for relation_id, source, relation_type, target in relation_specs
    )
    frame = ReferenceFrame(
        frame_id=frame_id,
        label=f"{domain} fixture frame",
        scope=FrameScope.LOCAL,
        coordinate_names=("row", "column"),
        units=("m", "m"),
        positive_directions=(PositiveDirection.INCREASING, PositiveDirection.INCREASING),
        provenance_ids=(seed_provenance_id,),
    )
    support = Support(
        support_id=support_id,
        support_kind=SupportKind.REGULAR_GRID,
        dimension_names=("row", "column"),
        shape=(2, 3),
        reference_frame_id=frame_id,
        provenance_ids=(seed_provenance_id,),
    )
    definition = FieldDefinition(
        field_id=field_definition_id,
        canonical_name=field_name,
        unit=unit,
        value_kind=ValueKind.CONTINUOUS,
        physical_rank=PhysicalRank.SCALAR,
        admissible_support_kinds=(SupportKind.REGULAR_GRID,),
        provenance_ids=(seed_provenance_id,),
    )
    representation_ref = _ref(SubjectKind.REPRESENTATION, representation_id, "v1")
    binding = FieldBinding(
        binding_id=field_binding_id,
        field_definition_id=field_definition_id,
        subject=_ref(SubjectKind.ENTITY, primary_entity_id),
        world_state_id=state_id,
        representation=representation_ref,
        support_id=support_id,
        scale_label="fixture-scale",
        provenance_ids=(data_provenance_id,),
    )
    state = WorldState(
        state_id=state_id,
        world_id=prefix + "world",
        role=WorldStateRole.GROUND_TRUTH,
        field_binding_ids=(field_binding_id,),
        representation_refs=(representation_ref,),
        provenance_ids=(data_provenance_id,),
    )
    seed_outputs = tuple(
        [
            *(_ref(SubjectKind.ENTITY, entity.entity_id) for entity in entities),
            *(_ref(SubjectKind.RELATION, relation.relation_id) for relation in relations),
            _ref(SubjectKind.SUPPORT, support_id),
            _ref(SubjectKind.FIELD_DEFINITION, field_definition_id),
        ]
    )
    seed_provenance = Provenance(
        provenance_id=seed_provenance_id,
        activity_type="fixture_construction",
        method="explicit cross-domain semantic fixture",
        outputs=seed_outputs,
    )
    data_provenance = Provenance(
        provenance_id=data_provenance_id,
        activity_type="deterministic_fixture_values",
        method="fixed numerical values for contract testing",
        inputs=(
            _ref(SubjectKind.ENTITY, primary_entity_id),
            _ref(SubjectKind.FIELD_DEFINITION, field_definition_id),
        ),
        outputs=(
            _ref(SubjectKind.FIELD_BINDING, field_binding_id),
            representation_ref,
            _ref(SubjectKind.WORLD_STATE, state_id),
        ),
        parent_provenance_ids=(seed_provenance_id,),
    )
    dataset = xr.Dataset(
        {field_name: (("row", "column"), np.arange(6, dtype=np.float64).reshape(2, 3))},
        coords={"row": np.arange(2), "column": np.arange(3)},
    )
    bundle = create_xarray_bundle(
        dataset,
        world_id=state.world_id,
        state=state,
        support=support,
        reference_frame=frame,
        representation_id=representation_id,
        version="v1",
        variable_bindings={field_name: binding},
        field_definitions=(definition,),
        provenance=data_provenance,
    )

    observation_representation_ref = _ref(
        SubjectKind.REPRESENTATION,
        observation_representation_id,
        "v1",
    )
    observation = Observation(
        observation_id=observation_id,
        world_id=state.world_id,
        status=ObservationStatus.SYNTHETIC,
        subjects=(
            _ref(SubjectKind.FIELD_DEFINITION, field_definition_id),
            _ref(SubjectKind.WORLD_STATE, state_id),
            _ref(SubjectKind.SUPPORT, support_id),
        ),
        representation=observation_representation_ref,
        quality=(("fixture", True),),
        provenance_ids=(observation_provenance_id,),
    )
    observation_representation = Representation(
        representation_id=observation_representation_id,
        version="v1",
        subjects=(_ref(SubjectKind.OBSERVATION, observation_id),),
        kind=RepresentationKind.ARRAY,
        artifact_uri=f"memory://{observation_representation_id}/v1",
        content_sha256=hashlib.sha256(observation_type.encode()).hexdigest(),
        media_type="application/octet-stream",
        support_id=support_id,
        reference_frame_id=frame_id,
        dimensions=support.dimension_names,
        provenance_ids=(observation_provenance_id,),
    )
    observation_provenance = Provenance(
        provenance_id=observation_provenance_id,
        activity_type="synthetic_observation",
        method=observation_type,
        inputs=(
            _ref(SubjectKind.WORLD_STATE, state_id),
            _ref(SubjectKind.FIELD_DEFINITION, field_definition_id),
        ),
        outputs=(
            _ref(SubjectKind.OBSERVATION, observation_id),
            observation_representation_ref,
        ),
        parent_provenance_ids=(data_provenance_id,),
    )

    world = World(
        world_id=state.world_id,
        label=f"{domain.title()} semantic fixture",
        origin=WorldOrigin.SYNTHETIC,
        entities=entities,
        relations=relations,
        field_definitions=(definition,),
        field_bindings=(binding,),
        representations=(bundle.representation, observation_representation),
        states=(state,),
        observations=(observation,),
        provenance=(seed_provenance, data_provenance, observation_provenance),
        reference_frames=(frame,),
        supports=(support,),
    )
    return KernelFixture(
        domain=domain,
        world=world,
        bundle=bundle,
        primary_entity_id=primary_entity_id,
        field_definition_id=field_definition_id,
        field_binding_id=field_binding_id,
        state_id=state_id,
        support_id=support_id,
    )
