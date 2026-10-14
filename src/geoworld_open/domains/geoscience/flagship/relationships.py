"""Compatibility adapter: explicit flagship objects, reusable spatial assessment."""
from hashlib import sha256

import numpy as np

from geoworld_open.domains.geoscience.flagship.input import (
    CompiledFlagshipInput,
    flagship_input_sha256,
)
from geoworld_open.domains.geoscience.flagship.integration import (
    FLAGSHIP_INPUT_ARTIFACT_URI,
    FLAGSHIP_INPUT_REPRESENTATION_ID,
    FLAGSHIP_INPUT_REPRESENTATION_VERSION,
    FRAME_ID,
    TRAJECTORY_REPRESENTATION_ID,
    TRAJECTORY_SUPPORT_ID,
)
from geoworld_open.domains.geoscience.flagship.numerics import well_trajectory_csv_bytes
from geoworld_open.domains.geoscience.relationships import (
    SpatialObject,
    _attach_geometry_verification,
    derive_relationships,
)
from geoworld_open.domains.geoscience.structural.relationships import structural_objects
from geoworld_open.reference.spatial import CellRegion, GeometryFrame, Polyline, UnknownGeometry
from geoworld_open.world import (
    RepresentationKind,
    SubjectKind,
    SubjectRef,
    SupportKind,
)


def _registered_representation(world, ref):
    matches=[item for item in world.representations if item.ref==ref]
    if len(matches)!=1:
        raise ValueError('expected one exact registered Representation version')
    return matches[0]


def _ref(kind, subject_id, version=None):
    return SubjectRef(kind=kind,subject_id=subject_id,representation_version=version)


def _flagship_spatial_objects(world, structural_result, inputs):
    """Reconstruct flagship geometries from their exact source contracts."""
    if not isinstance(inputs,CompiledFlagshipInput):
        raise ValueError('flagship relationships require compiled flagship input')
    if structural_result.structural_input!=inputs.structural:
        raise ValueError('flagship input differs from the completed structural input')
    state_id=structural_result.final_state_id
    state=world.state(state_id)
    structural_input_ref=_ref(
        SubjectKind.REPRESENTATION,
        'representation:structural-input',
        'v1',
    )
    flagship_input_ref=_ref(
        SubjectKind.REPRESENTATION,
        FLAGSHIP_INPUT_REPRESENTATION_ID,
        FLAGSHIP_INPUT_REPRESENTATION_VERSION,
    )
    flagship_input_rep=_registered_representation(world,flagship_input_ref)
    if (
        flagship_input_rep.kind!=RepresentationKind.TABLE
        or flagship_input_rep.artifact_uri!=FLAGSHIP_INPUT_ARTIFACT_URI
        or flagship_input_rep.content_sha256!=flagship_input_sha256(inputs)
        or structural_input_ref not in flagship_input_rep.derived_from
        or _ref(SubjectKind.WORLD_STATE,state_id) not in flagship_input_rep.subjects
    ):
        raise ValueError('compiled flagship input differs from its exact World-bound source')
    input_provenance=next(
        (
            item for item in world.provenance
            if item.provenance_id in flagship_input_rep.provenance_ids
            and flagship_input_ref in item.outputs
            and item.method=='canonical_flagship_input_json_v1'
        ),
        None,
    )
    if (
        input_provenance is None
        or structural_input_ref not in input_provenance.inputs
        or ('content_sha256',flagship_input_rep.content_sha256) not in input_provenance.parameters
    ):
        raise ValueError('flagship input Representation lacks matching source provenance')

    formation_id=f'formation:{inputs.reservoir_region.formation_id}'
    fault_id=f'fault:{inputs.reservoir_region.intersecting_fault_id}'
    well_id=f'well:{inputs.well.id}'
    region_id=f'reservoir-region:{inputs.reservoir_region.id}'
    formations={item.id:item for item in inputs.structural.formations}
    target_formation=formations.get(inputs.reservoir_region.formation_id)
    if target_formation is None or not target_formation.is_reservoir:
        raise ValueError('authored ReservoirRegion does not identify a reservoir Formation')
    if not any(item.kind=='fault' and f'fault:{item.id}'==fault_id for item in inputs.structural.structures):
        raise ValueError('authored ReservoirRegion does not identify a compiled Fault')

    region_entity=next((item for item in world.entities if item.entity_id==region_id),None)
    if region_entity is None or region_entity.entity_type!='geoscience:reservoir_region':
        raise ValueError('authored ReservoirRegion Entity is absent or has an incompatible type')
    semantics=next(
        (
            item for item in world.provenance
            if 'provenance:flagship-semantics'==item.provenance_id
            and _ref(SubjectKind.ENTITY,region_id) in item.outputs
        ),
        None,
    )
    if (
        semantics is None
        or flagship_input_ref not in semantics.inputs
        or _ref(SubjectKind.ENTITY,formation_id) not in semantics.inputs
        or 'provenance:flagship-input' not in semantics.parent_provenance_ids
    ):
        raise ValueError('ReservoirRegion identity is not linked to its authored Formation input')

    structural_objects_by_id={
        obj.entity_id:obj
        for obj in structural_objects(structural_result)
        if obj.entity_id in {formation_id,fault_id}
    }
    formation_obj=structural_objects_by_id.get(formation_id)
    if formation_obj is None or structural_objects_by_id.get(fault_id) is None:
        raise ValueError('flagship Formation or Fault lacks verified structural geometry')
    objects=[formation_obj,structural_objects_by_id[fault_id]]

    stratigraphy_bundle=structural_result.stratigraphy_bundle
    stratigraphy_rep=_registered_representation(world,stratigraphy_bundle.representation.ref)
    if stratigraphy_rep!=stratigraphy_bundle.representation:
        raise ValueError('flagship source bundle differs from its exact World Representation')
    data=stratigraphy_bundle.to_dataset()
    layer_index=np.asarray(data['layer_index'].values)
    selection=np.asarray(data['reservoir_selection'].values)
    if selection.dtype.kind!='b' or selection.shape!=layer_index.shape:
        raise ValueError('reservoir_selection has incompatible type or geometric support')
    formation_membership=layer_index==target_formation.order
    evidence=(stratigraphy_rep.ref,flagship_input_ref)
    geometry_frame=GeometryFrame(frame_id=FRAME_ID)
    if np.array_equal(selection,formation_membership):
        region_geometry=CellRegion(
            frame=geometry_frame,
            x_edges=formation_obj.geometry.x_edges,
            depth_edges=formation_obj.geometry.depth_edges,
            membership=tuple(tuple(bool(value) for value in row) for row in selection),
        )
    else:
        region_geometry=UnknownGeometry(
            frame=geometry_frame,
            reason='The declared reservoir_selection does not isolate the authored ReservoirRegion Formation.',
        )
    region=SpatialObject(
        entity_id=region_id,
        role='region',
        geometry=region_geometry,
        evidence=evidence,
        part_of_target_id=formation_id,
    )
    objects.append(
        _attach_geometry_verification(
            world,
            state_id,
            region,
            adapter_id='flagship',
            context=(world,structural_result,inputs),
        )
    )

    trajectory_ref=_ref(
        SubjectKind.REPRESENTATION,
        TRAJECTORY_REPRESENTATION_ID,
        'v1',
    )
    trajectory=_registered_representation(world,trajectory_ref)
    trajectory_bytes=well_trajectory_csv_bytes(inputs)
    support=next((item for item in world.supports if item.support_id==TRAJECTORY_SUPPORT_ID),None)
    frame=next((item for item in world.reference_frames if item.frame_id==FRAME_ID),None)
    trajectory_provenance=next(
        (
            item for item in world.provenance
            if 'provenance:flagship-well-trajectory'==item.provenance_id
            and trajectory_ref in item.outputs
        ),
        None,
    )
    if (
        trajectory.kind!=RepresentationKind.CURVE
        or trajectory.subjects!=(_ref(SubjectKind.ENTITY,well_id),)
        or trajectory.content_sha256!=sha256(trajectory_bytes).hexdigest()
        or trajectory.support_id!=TRAJECTORY_SUPPORT_ID
        or trajectory.reference_frame_id!=FRAME_ID
        or trajectory.derived_from!=(flagship_input_ref,)
        or support is None
        or support.support_kind!=SupportKind.CURVE
        or support.reference_frame_id!=FRAME_ID
        or support.dimension_names!=('depth',)
        or support.shape!=(2,)
        or frame is None
        or frame.coordinate_names!=('depth','x')
        or frame.units!=('m','m')
        or tuple(value.value for value in frame.positive_directions)!=('down','increasing')
        or trajectory_provenance is None
        or trajectory_provenance.method!='explicit vertical 2-D trajectory endpoints'
        or flagship_input_ref not in trajectory_provenance.inputs
        or _ref(SubjectKind.ENTITY,well_id) not in trajectory_provenance.inputs
        or _ref(SubjectKind.SUPPORT,TRAJECTORY_SUPPORT_ID) not in trajectory_provenance.outputs
        or 'provenance:flagship-semantics' not in trajectory_provenance.parent_provenance_ids
    ):
        raise ValueError('well trajectory differs from the exact entity- and state-bound source')
    well=SpatialObject(
        entity_id=well_id,
        role='well',
        geometry=Polyline(
            frame=geometry_frame,
            vertices=(
                (inputs.well.x_m,inputs.well.top_depth_m),
                (inputs.well.x_m,inputs.well.bottom_depth_m),
            ),
        ),
        evidence=(trajectory_ref,flagship_input_ref),
    )
    objects.append(
        _attach_geometry_verification(
            world,
            state_id,
            well,
            adapter_id='flagship',
            context=(world,structural_result,inputs),
        )
    )

    return tuple(objects)


def _verify_flagship_spatial_object(world,state_id,obj,context):
    if not isinstance(context,tuple) or len(context)!=3:
        raise ValueError('flagship geometry verification context is invalid')
    source_world,structural_result,inputs=context
    if world.world_id!=source_world.world_id or state_id!=structural_result.final_state_id:
        raise ValueError('flagship geometry verification has incompatible WorldState context')
    expected=next(
        (
            item for item in _flagship_spatial_objects(*context)
            if item.entity_id==obj.entity_id
        ),
        None,
    )
    if expected is None or expected.model_dump(mode='json')!=obj.model_dump(mode='json'):
        raise ValueError('flagship geometry is not the verified extraction from its source data')
    source_representations={item.ref:item for item in source_world.representations}
    current_representations={item.ref:item for item in world.representations}
    if any(
        source_representations.get(ref)!=current_representations.get(ref)
        for ref in obj.evidence
    ):
        raise ValueError('flagship geometry source differs from the admitted World')


def flagship_relationships(world,structural_result,inputs):
    """Derive flagship claims only from verified, source-bound geometries."""
    objects=_flagship_spatial_objects(world,structural_result,inputs)

    roles={obj.entity_id:obj.role for obj in objects}

    def compatibility_id(source,relation,target):
        return 'relation:flagship-'+roles[source]+'-'+relation.split(':')[-1].replace('_','-')+'-'+roles[target]

    return derive_relationships(
        world,
        structural_result.final_state_id,
        objects,
        relation_id=compatibility_id,
    )
