"""Authored semantic roles applied to independently assessed spatial predicates."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Literal, Callable
from pydantic import Field
from geoworld_open.reference.spatial import Geometry, CellRegion, Polyline, UnknownGeometry, SpatialAssessment, contained_by, curve_region
from geoworld_open.standard.capabilities import ContractModel
from geoworld_open.sdk.serialization import canonical_json_bytes
from geoworld_open.world import World, SubjectRef, SubjectKind, Relation, Representation, RepresentationKind, Provenance


class SpatialObject(ContractModel):
    entity_id: str
    role: Literal['region', 'formation', 'well', 'fault']
    geometry: Geometry
    evidence: tuple[SubjectRef, ...] = Field(min_length=1)
    # Geometry alone cannot establish geological PART_OF semantics.
    part_of_target_id: str | None = None


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
    Caller geometries must originate in verified representation-backed data.
    """
    world.state(state_id)
    entities={item.entity_id:item for item in world.entities}
    frames={item.frame_id:item for item in world.reference_frames}
    representations={item.ref for item in world.representations}
    if len({obj.entity_id for obj in objects})!=len(objects):
        raise ValueError('spatial objects must have distinct entity IDs')
    objects=tuple(sorted(objects,key=lambda obj:obj.entity_id))
    for obj in objects:
        entity=entities.get(obj.entity_id)
        expected={'region':'geoscience:reservoir_region','formation':'geoscience:formation','well':'geoscience:well','fault':'geoscience:fault'}[obj.role]
        if entity is None or entity.entity_type!=expected:
            raise ValueError('semantic roles must match registered Entity types')
        frame=frames.get(obj.geometry.frame.frame_id)
        if frame is None or frame.coordinate_names!=('depth','x') or any(unit not in {'m','km'} for unit in frame.units) or tuple(direction.value for direction in frame.positive_directions)!=('down','increasing'):
            raise ValueError('geometry requires a registered compatible depth/x frame')
        if any(ref.kind!=SubjectKind.REPRESENTATION or ref not in representations for ref in obj.evidence):
            raise ValueError('geometry evidence must reference registered exact Representation versions')
        if obj.part_of_target_id and obj.part_of_target_id not in entities:
            raise ValueError('authored part-of target is absent')
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
