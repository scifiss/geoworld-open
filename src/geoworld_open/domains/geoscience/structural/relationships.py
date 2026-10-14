"""Representation-backed adapter for the current structural reference supports."""
from __future__ import annotations

import numpy as np

from geoworld_open.domains.geoscience.structural.input import (
    CompiledFault,
    CompiledFold,
    structural_input_sha256,
)
from geoworld_open.domains.geoscience.structural.integration import (
    FINAL_STATE_ID,
    FRAME_ID,
    INITIAL_STATE_ID,
    INPUT_ARTIFACT_URI,
    INPUT_REPRESENTATION_ID,
    INPUT_REPRESENTATION_VERSION,
    SUPPORT_ID,
    StructuralWorldResult,
)
from geoworld_open.domains.geoscience.relationships import (
    SpatialObject,
    _attach_geometry_verification,
)
from geoworld_open.reference.spatial import (
    CellRegion,
    GeometryFrame,
    Polyline,
    UnknownGeometry,
)
from geoworld_open.world import (
    SubjectKind,
    SubjectRef,
    SupportKind,
    WorldStateRole,
    dataset_content_sha256,
)


def _registered_representation(world, ref):
    matches=[item for item in world.representations if item.ref==ref]
    if len(matches)!=1:
        raise ValueError('expected one exact registered Representation version')
    return matches[0]


def _require_binding(world, state, bundle, variable_name, definition_name):
    binding_ids=dict(bundle.variable_bindings)
    binding_id=binding_ids.get(variable_name)
    binding=next((item for item in world.field_bindings if item.binding_id==binding_id),None)
    if (
        binding is None
        or binding.world_state_id!=state.state_id
        or binding.binding_id not in state.field_binding_ids
        or binding.representation!=bundle.representation.ref
        or binding.support_id!=SUPPORT_ID
        or binding.subject.kind!=SubjectKind.SUPPORT
        or binding.subject.subject_id!=SUPPORT_ID
    ):
        raise ValueError(f'{variable_name} lacks a state-specific support binding')
    definition=next(
        (item for item in world.field_definitions if item.field_id==binding.field_definition_id),
        None,
    )
    if definition is None or definition.canonical_name!=definition_name:
        raise ValueError(f'{variable_name} FieldBinding has an incompatible definition')
    expected=SubjectRef(kind=SubjectKind.FIELD_BINDING,subject_id=binding_id)
    if expected not in bundle.representation.subjects:
        raise ValueError(f'{variable_name} Representation does not bind its FieldBinding')
    return binding


def structural_objects(result):
    """Extract only geometry whose bytes and semantic source chain are verified.

    Formation masks come from the content-verified ``layer_index`` field. Fault
    traces are deterministic analytic derivations from the exact compiled input;
    displaced-side masks are never interpreted as fault surfaces.
    """
    world=result.world
    compiled=result.structural_input
    if result.final_state_id!=FINAL_STATE_ID:
        raise ValueError('structural geometry requires the supported final WorldState')
    initial_state=world.state(INITIAL_STATE_ID)
    final_state=world.state(FINAL_STATE_ID)
    if (
        initial_state.role!=WorldStateRole.HYPOTHETICAL
        or final_state.parent_state_id!=INITIAL_STATE_ID
        or final_state.role!=WorldStateRole.SIMULATED
    ):
        raise ValueError('structural geometry has an unsupported WorldState lineage')

    input_ref=SubjectRef(
        kind=SubjectKind.REPRESENTATION,
        subject_id=INPUT_REPRESENTATION_ID,
        representation_version=INPUT_REPRESENTATION_VERSION,
    )
    input_representation=_registered_representation(world,input_ref)
    if (
        input_ref not in initial_state.representation_refs
        or input_representation.content_sha256!=structural_input_sha256(compiled)
        or input_representation.artifact_uri!=INPUT_ARTIFACT_URI
        or input_representation.kind.value!='table'
    ):
        raise ValueError('compiled structural input does not match its exact World-bound source')
    input_provenance=next(
        (
            item for item in world.provenance
            if input_ref in item.outputs
            and item.method=='canonical_structural_input_json_v1'
        ),
        None,
    )
    if input_provenance is None or ('content_sha256',input_representation.content_sha256) not in input_provenance.parameters:
        raise ValueError('structural input Representation lacks matching source provenance')

    stratigraphy_bundle=result.stratigraphy_bundle
    stratigraphy_rep=stratigraphy_bundle.representation
    registered_stratigraphy=_registered_representation(world,stratigraphy_rep.ref)
    if registered_stratigraphy!=stratigraphy_rep:
        raise ValueError('stratigraphy bundle Representation differs from the World record')
    if dataset_content_sha256(stratigraphy_bundle.to_dataset())!=stratigraphy_rep.content_sha256:
        raise ValueError('stratigraphy bundle content differs from its Representation hash')
    if (
        stratigraphy_rep.ref not in final_state.representation_refs
        or stratigraphy_rep.support_id!=SUPPORT_ID
        or stratigraphy_rep.reference_frame_id!=FRAME_ID
    ):
        raise ValueError('stratigraphy Representation is not bound to its declared grid and state')
    support=next((item for item in world.supports if item.support_id==SUPPORT_ID),None)
    frame=next((item for item in world.reference_frames if item.frame_id==FRAME_ID),None)
    expected_shape=(compiled.grid.ndepth,compiled.grid.nx)
    if (
        support is None
        or support.support_kind!=SupportKind.REGULAR_GRID
        or support.dimension_names!=('depth','x')
        or support.shape!=expected_shape
        or support.reference_frame_id!=FRAME_ID
        or frame is None
        or frame.coordinate_names!=('depth','x')
        or frame.units!=('m','m')
        or tuple(value.value for value in frame.positive_directions)!=('down','increasing')
    ):
        raise ValueError('structural Representation uses an incompatible coordinate support')
    if not {'depth','x'}.issubset(set(stratigraphy_rep.dimensions)):
        raise ValueError('stratigraphy Representation omits its spatial dimensions')

    provenance=next(
        (
            item for item in world.provenance
            if item.provenance_id in stratigraphy_rep.provenance_ids
            and item.method=='explicit_layer_lookup_v1'
            and stratigraphy_rep.ref in item.outputs
        ),
        None,
    )
    if provenance is None or input_ref not in provenance.inputs:
        raise ValueError('stratigraphy Representation lacks source-linked derivation provenance')
    layer_values=tuple(
        SubjectRef(kind=SubjectKind.ENTITY,subject_id=f'formation:{formation.id}')
        for formation in compiled.formations
    )
    if any(ref not in provenance.inputs for ref in layer_values):
        raise ValueError('stratigraphy derivation does not bind its compiled Formation identities')

    data=stratigraphy_bundle.to_dataset()
    x=compiled.grid.x_origin_m+np.arange(compiled.grid.nx+1)*compiled.grid.dx_m
    z=compiled.grid.depth_origin_m+np.arange(compiled.grid.ndepth+1)*compiled.grid.ddepth_m
    expected_x=compiled.grid.x_origin_m+(np.arange(compiled.grid.nx)+.5)*compiled.grid.dx_m
    expected_z=compiled.grid.depth_origin_m+(np.arange(compiled.grid.ndepth)+.5)*compiled.grid.ddepth_m
    if (
        data.sizes.get('depth')!=compiled.grid.ndepth
        or data.sizes.get('x')!=compiled.grid.nx
        or not np.array_equal(data.x.values,expected_x)
        or not np.array_equal(data.depth.values,expected_z)
    ):
        raise ValueError('formation coordinates do not match the source grid')
    layer_index=data['layer_index']
    if (
        layer_index.dims!=('depth','x')
        or layer_index.attrs.get('units')!='1'
        or layer_index.attrs.get('method_id')!='explicit_layer_lookup_v1'
        or layer_index.dtype.kind not in {'i','u'}
    ):
        raise ValueError('formation geometry requires the declared layer-index support')
    _require_binding(world,final_state,stratigraphy_bundle,'layer_index','layer_index')

    reservoir=data['reservoir_selection']
    if (
        reservoir.dims!=('depth','x')
        or reservoir.attrs.get('units')!='1'
        or reservoir.attrs.get('method_id')!='explicit_layer_lookup_v1'
        or reservoir.dtype.kind!='b'
    ):
        raise ValueError('reservoir geometry requires the declared Boolean selection support')
    _require_binding(world,final_state,stratigraphy_bundle,'reservoir_selection','reservoir_selection')
    layer_array=np.asarray(layer_index.values)
    if not np.isin(layer_array,tuple(item.order for item in compiled.formations)).all():
        raise ValueError('layer-index contents are outside the compiled Formation domain')
    expected_reservoir=np.isin(
        layer_array,
        tuple(item.order for item in compiled.formations if item.is_reservoir),
    )
    if not np.array_equal(np.asarray(reservoir.values,dtype=bool),expected_reservoir):
        raise ValueError('reservoir_selection contents disagree with the compiled source roles')

    frame_geometry=GeometryFrame(frame_id=FRAME_ID)
    evidence=(stratigraphy_rep.ref,)
    objects=[]
    for formation in compiled.formations:
        entity_id=f'formation:{formation.id}'
        if not any(ref.subject_id==entity_id for ref in layer_values):
            raise ValueError('Formation geometry has no explicit compiled Entity identity')
        geometry=CellRegion(
            frame=frame_geometry,
            x_edges=tuple(x),
            depth_edges=tuple(z),
            membership=tuple(
                tuple(bool(value) for value in row)
                for row in (layer_array==formation.order)
            ),
        )
        obj=SpatialObject(entity_id=entity_id,role='formation',geometry=geometry,evidence=evidence)
        objects.append(
            _attach_geometry_verification(
                world,
                FINAL_STATE_ID,
                obj,
                adapter_id='structural',
                context=result,
            )
        )

    geometry_representation=_registered_representation(world,result.geometry_bundle.representation.ref)
    if geometry_representation!=result.geometry_bundle.representation:
        raise ValueError('structural geometry bundle differs from the World Representation')
    if dataset_content_sha256(result.geometry_bundle.to_dataset())!=geometry_representation.content_sha256:
        raise ValueError('structural geometry content differs from its Representation hash')
    geometry_provenance=next(
        (
            item for item in world.provenance
            if item.provenance_id in geometry_representation.provenance_ids
            and item.method=='analytic_source_depth_v1'
            and geometry_representation.ref in item.outputs
        ),
        None,
    )
    if geometry_provenance is None or input_ref not in geometry_provenance.inputs:
        raise ValueError('analytic structural geometry is not linked to the exact compiled input')
    source_entities={item.subject_id for item in geometry_provenance.inputs if item.kind==SubjectKind.ENTITY}
    if source_entities!={f'{item.kind}:{item.id}' for item in compiled.structures}:
        raise ValueError('analytic geometry provenance does not bind the compiled structure identities')

    folds=[]
    previous_fault=False
    for index,structure in enumerate(compiled.structures):
        if isinstance(structure,CompiledFold):
            folds.append(structure)
            continue
        assert isinstance(structure,CompiledFault)
        if previous_fault or index!=len(compiled.structures)-1:
            geometry=UnknownGeometry(
                frame=frame_geometry,
                reason='Sequential fault/surface advection is not represented; fault-side masks are not fault surfaces.',
            )
        else:
            direction=1 if structure.dip_direction=='positive_x' else -1
            depths=structure.reference_depth_m+(x-structure.x_position_m)*np.tan(np.deg2rad(structure.dip_deg))/direction
            error=0.
            for fold in folds:
                depths+=fold.amplitude_m*np.sin(2*np.pi*(x-fold.x_origin_m)/fold.wavelength_m+np.deg2rad(fold.phase_deg))
                error+=abs(fold.amplitude_m)*(2*np.pi/fold.wavelength_m)**2*compiled.grid.dx_m**2/8
            geometry=Polyline(frame=frame_geometry,vertices=tuple(zip(x,depths)),approximation_error_m=float(error))
        entity_id=f'fault:{structure.id}'
        entity_ref=SubjectRef(kind=SubjectKind.ENTITY,subject_id=entity_id)
        if entity_ref not in geometry_provenance.inputs:
            raise ValueError('fault trace lacks explicit source Entity provenance')
        obj=SpatialObject(entity_id=entity_id,role='fault',geometry=geometry,evidence=(input_ref,))
        objects.append(
            _attach_geometry_verification(
                world,
                FINAL_STATE_ID,
                obj,
                adapter_id='structural',
                context=result,
            )
        )
        previous_fault=True
    return tuple(objects)


def _verify_structural_spatial_object(world,state_id,obj,context):
    if (
        not isinstance(context,StructuralWorldResult)
        or world.world_id!=context.world.world_id
        or state_id!=context.final_state_id
    ):
        raise ValueError('structural geometry verification context is invalid')
    expected=next(
        (
            item for item in structural_objects(context)
            if item.entity_id==obj.entity_id
        ),
        None,
    )
    if expected is None or expected.model_dump(mode='json')!=obj.model_dump(mode='json'):
        raise ValueError('structural geometry is not the verified extraction from its source data')
    context_representations={item.ref:item for item in context.world.representations}
    current_representations={item.ref:item for item in world.representations}
    if any(
        context_representations.get(ref)!=current_representations.get(ref)
        for ref in obj.evidence
    ):
        raise ValueError('structural geometry source differs from the admitted World')
