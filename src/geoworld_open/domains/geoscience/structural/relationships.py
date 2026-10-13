"""Representation-backed adapter for the current structural reference supports."""
from __future__ import annotations
import numpy as np
from geoworld_open.domains.geoscience.structural.input import CompiledFold, CompiledFault, structural_input_sha256
from geoworld_open.domains.geoscience.structural.integration import FRAME_ID, FINAL_STATE_ID
from geoworld_open.domains.geoscience.relationships import SpatialObject
from geoworld_open.reference.spatial import GeometryFrame, CellRegion, Polyline, UnknownGeometry


def structural_objects(result):
    """Read immutable bundles; never treat displaced-side selection as a surface.

    A curved fault trace is sampled from its defining equation, with the standard
    linear-interpolation second-derivative error bound. Earlier faults or later
    deformations require a surface-advection operator we do not currently have.
    """
    data=result.stratigraphy_bundle.to_dataset()
    compiled=result.structural_input
    world=result.world
    frame=GeometryFrame(frame_id=FRAME_ID)
    x=compiled.grid.x_origin_m+np.arange(compiled.grid.nx+1)*compiled.grid.dx_m
    z=compiled.grid.depth_origin_m+np.arange(compiled.grid.ndepth+1)*compiled.grid.ddepth_m
    evidence=(result.stratigraphy_bundle.representation.ref,)
    if not any(rep.ref==evidence[0] and rep.content_sha256==result.stratigraphy_bundle.representation.content_sha256 for rep in world.representations):
        raise ValueError('stratigraphy bundle does not match the World evidence')
    input_rep=next(rep for rep in world.representations if rep.representation_id=='representation:structural-input')
    if input_rep.content_sha256!=structural_input_sha256(compiled):
        raise ValueError('compiled geometry does not match the World-bound input')
    expected_x=compiled.grid.x_origin_m+(np.arange(compiled.grid.nx)+.5)*compiled.grid.dx_m
    expected_z=compiled.grid.depth_origin_m+(np.arange(compiled.grid.ndepth)+.5)*compiled.grid.ddepth_m
    if not np.array_equal(data.x.values,expected_x) or not np.array_equal(data.depth.values,expected_z):
        raise ValueError('formation coordinates do not match the compiled grid')
    if data['layer_index'].dims!=('depth','x') or data['layer_index'].attrs.get('units')!='1':
        raise ValueError('formation geometry requires the declared layer-index support')
    objects=[]
    for formation in compiled.formations:
        mask=data['layer_index'].values==formation.order
        geometry=CellRegion(frame=frame,x_edges=tuple(x),depth_edges=tuple(z),membership=tuple(tuple(bool(v) for v in row) for row in mask))
        objects.append(SpatialObject(entity_id='formation:'+formation.id,role='formation',geometry=geometry,evidence=evidence))
    input_ref=input_rep.ref
    folds=[];previous_fault=False
    for index,structure in enumerate(compiled.structures):
        if isinstance(structure,CompiledFold):
            folds.append(structure);continue
        assert isinstance(structure,CompiledFault)
        if previous_fault or index!=len(compiled.structures)-1:
            geometry=UnknownGeometry(frame=frame,reason='Sequential fault/surface advection is not represented; fault-side masks are not fault surfaces.')
        else:
            direction=1 if structure.dip_direction=='positive_x' else -1
            depths=structure.reference_depth_m+(x-structure.x_position_m)*np.tan(np.deg2rad(structure.dip_deg))/direction
            error=0.
            for fold in folds:
                depths+=fold.amplitude_m*np.sin(2*np.pi*(x-fold.x_origin_m)/fold.wavelength_m+np.deg2rad(fold.phase_deg))
                error+=abs(fold.amplitude_m)*(2*np.pi/fold.wavelength_m)**2*compiled.grid.dx_m**2/8
            geometry=Polyline(frame=frame,vertices=tuple(zip(x,depths)),approximation_error_m=float(error))
        objects.append(SpatialObject(entity_id='fault:'+structure.id,role='fault',geometry=geometry,evidence=(input_ref,)))
        previous_fault=True
    return tuple(objects)
