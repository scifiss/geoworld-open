"""Authored semantic roles applied to independently assessed spatial predicates."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Literal, Callable
from pydantic import Field, PrivateAttr
from geoworld_open.reference.spatial import Geometry, CellRegion, Polyline, UnknownGeometry, SpatialAssessment, contained_by, curve_region
from geoworld_open.standard.capabilities import ContractModel
from geoworld_open.sdk.serialization import canonical_json_bytes
from geoworld_open.world import World, SubjectRef, SubjectKind, Relation, Representation, RepresentationKind, Provenance, WorldStateRole


class SpatialObject(ContractModel):
    entity_id: str
    role: Literal['region', 'formation', 'well', 'fault']
    geometry: Geometry
    evidence: tuple[SubjectRef, ...] = Field(min_length=1)
    # Geometry alone cannot establish geological PART_OF semantics.
    part_of_target_id: str | None = None
    _verification: _GeometryVerification | None = PrivateAttr(default=None)


@dataclass(frozen=True)
class _GeometryVerification:
    adapter_id: str
    world_id: str
    state_id: str
    object_sha256: str
    representations: tuple[Representation, ...]
    context: object


def _object_sha256(obj: SpatialObject) -> str:
    return sha256(canonical_json_bytes(obj)).hexdigest()


def _state_ancestry(world: World, state_id: str) -> tuple[str, ...]:
    states={item.state_id:item for item in world.states}
    if state_id not in states:
        raise ValueError('spatial evidence references an unknown WorldState')
    result=[]
    current=states[state_id]
    while True:
        result.append(current.state_id)
        if current.parent_state_id is None:
            return tuple(result)
        current=states[current.parent_state_id]


def _representation_state_compatible(
    world: World, ref: SubjectRef, allowed_states: set[str]
) -> bool:
    representations={item.ref:item for item in world.representations}
    provenance={item.provenance_id:item for item in world.provenance}
    visited_representations:set[SubjectRef]=set()
    visited_provenance:set[str]=set()

    def from_provenance(provenance_id: str) -> bool:
        if provenance_id in visited_provenance:
            return False
        visited_provenance.add(provenance_id)
        record=provenance.get(provenance_id)
        if record is None:
            return False
        if any(
            item.kind==SubjectKind.WORLD_STATE and item.subject_id in allowed_states
            for item in record.inputs
        ):
            return True
        if any(
            item.kind==SubjectKind.REPRESENTATION and from_representation(item)
            for item in record.inputs
        ):
            return True
        return any(from_provenance(parent) for parent in record.parent_provenance_ids)

    def from_representation(candidate: SubjectRef) -> bool:
        if candidate in visited_representations:
            return False
        visited_representations.add(candidate)
        representation=representations.get(candidate)
        if representation is None:
            return False
        if any(
            item.kind==SubjectKind.WORLD_STATE and item.subject_id in allowed_states
            for item in representation.subjects
        ):
            return True
        if any(
            state.state_id in allowed_states and candidate in state.representation_refs
            for state in world.states
        ):
            return True
        if any(from_representation(parent) for parent in representation.derived_from):
            return True
        return any(from_provenance(item) for item in representation.provenance_ids)

    return from_representation(ref)


def _validate_spatial_frame(world: World, obj: SpatialObject) -> None:
    frames={item.frame_id:item for item in world.reference_frames}
    geometry_frame=obj.geometry.frame
    frame=frames.get(geometry_frame.frame_id)
    if (
        frame is None
        or frame.coordinate_names!=('depth','x')
        or frame.units!=('m','m')
        or tuple(direction.value for direction in frame.positive_directions)!=('down','increasing')
        or geometry_frame.axes!='x_depth_positive_down'
        or geometry_frame.unit not in {'m','km'}
    ):
        raise ValueError('geometry frame is not compatible with the registered World frame')


def _attach_geometry_verification(
    world: World,
    state_id: str,
    obj: SpatialObject,
    *,
    adapter_id: str,
    context: object,
) -> SpatialObject:
    """Attach private adapter context; admission re-derives the geometry from it."""
    if obj.entity_id not in {item.entity_id for item in world.entities}:
        raise ValueError('geometry Entity is absent from the World')
    if obj.part_of_target_id is not None and obj.part_of_target_id not in {
        item.entity_id for item in world.entities
    }:
        raise ValueError('PART_OF target is absent from the World')
    _validate_spatial_frame(world,obj)
    ancestry=set(_state_ancestry(world,state_id))
    registered={item.ref:item for item in world.representations}
    source_records=[]
    for ref in obj.evidence:
        representation=registered.get(ref)
        if ref.kind!=SubjectKind.REPRESENTATION or representation is None:
            raise ValueError('geometry requires exact registered Representation versions')
        if not _representation_state_compatible(world,ref,ancestry):
            raise ValueError('geometry source Representation is outside the claimed WorldState lineage')
        source_records.append(representation)
    object.__setattr__(
        obj,
        '_verification',
        _GeometryVerification(
            adapter_id=adapter_id,
            world_id=world.world_id,
            state_id=state_id,
            object_sha256=_object_sha256(obj),
            representations=tuple(source_records),
            context=context,
        ),
    )
    return obj


def _require_verified_spatial_object(world: World, state_id: str, obj: SpatialObject) -> None:
    verification=obj._verification
    if verification is None:
        raise ValueError('caller-provided geometry is unverified; use a trusted source adapter')
    if verification.state_id!=state_id:
        raise ValueError('verified geometry is bound to a different WorldState')
    if verification.world_id!=world.world_id:
        raise ValueError('verified geometry is bound to a different World identity')
    if verification.object_sha256!=_object_sha256(obj):
        raise ValueError('verified geometry or its evidence binding changed after verification')
    _validate_spatial_frame(world,obj)
    ancestry=set(_state_ancestry(world,state_id))
    registered={item.ref:item for item in world.representations}
    if len(obj.evidence)!=len(verification.representations):
        raise ValueError('verified geometry Representation binding changed')
    for ref,verified_representation in zip(obj.evidence,verification.representations):
        if registered.get(ref)!=verified_representation:
            raise ValueError('registered Representation version or content identity changed')
        if not _representation_state_compatible(world,ref,ancestry):
            raise ValueError('geometry source Representation is outside the claimed WorldState lineage')
    if verification.adapter_id=='structural':
        from geoworld_open.domains.geoscience.structural.relationships import (
            _verify_structural_spatial_object,
        )
        _verify_structural_spatial_object(world,state_id,obj,verification.context)
    elif verification.adapter_id=='flagship':
        from geoworld_open.domains.geoscience.flagship.relationships import (
            _verify_flagship_spatial_object,
        )
        _verify_flagship_spatial_object(world,state_id,obj,verification.context)
    else:
        raise ValueError('geometry verification does not identify a trusted source adapter')


class RelationshipAssessment(ContractModel):
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    spatial: SpatialAssessment


class RelationshipEvidence(ContractModel):
    method: Literal['cell_union_relationships_v1'] = 'cell_union_relationships_v1'
    world_id: str
    state_id: str
    objects: tuple[SpatialObject, ...]
    assessments: tuple[RelationshipAssessment, ...]


@dataclass(frozen=True)
class RelationshipDerivation:
    world: World
    assessments: tuple[RelationshipAssessment, ...]
    representation: Representation
    evidence_bytes: bytes


def derive_relationships(world: World, state_id: str, objects: tuple[SpatialObject, ...], *,
                         tolerance_m=0., relation_id: Callable | None = None) -> RelationshipDerivation:
    """Append evidence and supported claims atomically; retain absent/unknown cases.

    This is semantic enrichment, not a new numerical state or ninth kernel type.
    Caller-supplied geometry is never authoritative: only source adapters that
    verified its exact Representation, derivation, entity, and state may seal it.
    """
    world.state(state_id)
    entities={item.entity_id:item for item in world.entities}
    if len({obj.entity_id for obj in objects})!=len(objects):
        raise ValueError('spatial objects must have distinct entity IDs')
    objects=tuple(sorted(objects,key=lambda obj:obj.entity_id))
    for obj in objects:
        entity=entities.get(obj.entity_id)
        expected={'region':'geoscience:reservoir_region','formation':'geoscience:formation','well':'geoscience:well','fault':'geoscience:fault'}[obj.role]
        if entity is None or entity.entity_type!=expected:
            raise ValueError('semantic roles must match registered Entity types')
        _require_verified_spatial_object(world,state_id,obj)
        if obj.part_of_target_id and obj.role!='region':
            raise ValueError('only explicitly authored ReservoirRegion objects may establish PART_OF')
    assessments=[]
    for source in objects:
        for target in objects:
            if source.entity_id==target.entity_id:
                continue
            if source.role=='region' and target.role in {'region','formation'} and source.part_of_target_id==target.entity_id:
                predicate,relation='contained_by','geoscience:part_of'
            elif source.role in {'well','fault'} and target.role in {'region','formation'}:
                predicate='penetrates' if source.role=='well' else 'intersects'
                relation='geoscience:'+predicate
            else:
                continue
            geometries=(source.geometry,target.geometry)
            if any(isinstance(item,UnknownGeometry) for item in geometries):
                reason='; '.join(item.reason for item in geometries if isinstance(item,UnknownGeometry))
                result=SpatialAssessment(predicate=predicate,status='indeterminate',reason=reason,tolerance_m=tolerance_m)
            elif predicate=='contained_by' and all(isinstance(item,CellRegion) for item in geometries):
                result=contained_by(*geometries,tolerance_m=tolerance_m)
            elif isinstance(source.geometry,Polyline) and isinstance(target.geometry,CellRegion):
                result=curve_region(*geometries,predicate=predicate,tolerance_m=tolerance_m)
            else:
                result=SpatialAssessment(predicate=predicate,status='indeterminate',reason='Geometry kinds do not support this predicate.',tolerance_m=tolerance_m)
            assessments.append(RelationshipAssessment(source_entity_id=source.entity_id,target_entity_id=target.entity_id,relation_type=relation,spatial=result))
    payload=RelationshipEvidence(world_id=world.world_id,state_id=state_id,objects=objects,assessments=tuple(assessments))
    evidence_bytes=canonical_json_bytes(payload)
    digest=sha256(evidence_bytes).hexdigest()
    pid='provenance:geometry-relationships:'+digest[:24]
    inputs=tuple(sorted({ref for obj in objects for ref in obj.evidence},key=lambda ref:ref.model_dump_json()))
    representation=Representation(representation_id='representation:geometry-relationships:'+digest[:24],version='v1',
        subjects=tuple(SubjectRef(kind=SubjectKind.ENTITY,subject_id=obj.entity_id) for obj in objects),
        kind=RepresentationKind.TABLE,artifact_uri='artifact://geometry/relationships-'+digest+'.json',
        media_type='application/json',content_sha256=digest,derived_from=inputs,provenance_ids=(pid,))
    relations=[]
    for assessment in assessments:
        if assessment.spatial.status!='present':
            continue
        triple=(assessment.source_entity_id,assessment.relation_type,assessment.target_entity_id)
        rid=relation_id(*triple) if relation_id else 'relation:geometry:'+sha256(json.dumps((triple,digest),separators=(',',':')).encode()).hexdigest()[:24]
        relations.append(Relation(relation_id=rid,source_entity_id=triple[0],relation_type=triple[1],target_entity_id=triple[2],
            valid_from_state_id=state_id,qualifiers=(('geometry_evidence_sha256',digest),('support_semantics','closed cell-union footprint')),
            provenance_ids=(pid,)))
    provenance=Provenance(provenance_id=pid,activity_type='geoscience:geometry_relationship_derivation',method=payload.method,
        inputs=(SubjectRef(kind=SubjectKind.WORLD_STATE,subject_id=state_id),*inputs,
                *(SubjectRef(kind=SubjectKind.ENTITY,subject_id=obj.entity_id) for obj in objects)),
        outputs=(representation.ref,*(SubjectRef(kind=SubjectKind.RELATION,subject_id=item.relation_id) for item in relations)),
        parameters=(('tolerance_m',tolerance_m),('evidence_sha256',digest)))
    # Idempotent admission of immutable records; conflicting identities fail closed.
    values=world.model_dump(mode='python')
    for name,records,key in [('relations',relations,lambda item:item.relation_id),
                            ('representations',[representation],lambda item:item.ref),
                            ('provenance',[provenance],lambda item:item.provenance_id)]:
        existing={key(item):item for item in getattr(world,name)}
        for item in records:
            if key(item) in existing and existing[key(item)]!=item:
                raise ValueError('conflicting immutable geometry-derived record')
            existing[key(item)]=item
        values[name]=tuple(existing.values())
    return RelationshipDerivation(World.model_validate(values),tuple(assessments),representation,evidence_bytes)
