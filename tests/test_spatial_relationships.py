"""Analytic and metamorphic expectations independent of the flagship example."""
import json
from pathlib import Path
from hashlib import sha256
import numpy as np
import pytest
import xarray as xr
from pydantic import ValidationError
from geoworld_open.reference.spatial import (
    GeometryFrame, CellRegion, Polyline, UnknownGeometry, GeometryQuery,
    curve_region, contained_by, SpatialPredicateCapability,
)
from geoworld_open.conformance import check_capability, check_world
from geoworld_open.sdk import CapabilityRegistry
from geoworld_open.domains.geoscience.flagship import load_flagship_spec, compile_flagship_input, bootstrap_flagship_semantics
from geoworld_open.domains.geoscience.flagship.relationships import flagship_relationships
from geoworld_open.domains.geoscience.structural import run_compiled_structural_world
from geoworld_open.domains.geoscience.structural.relationships import structural_objects
from geoworld_open.domains.geoscience.relationships import derive_relationships, SpatialObject

FRAME=GeometryFrame(frame_id='frame:test')
EXAMPLE=Path(__file__).parents[1]/'examples/scenarios/flagship_faulted_reservoir.yaml'


def region(n=2, *, unit='m', frame='frame:test', left=True):
    scale=1000 if unit=='km' else 1
    edges=tuple(np.linspace(0,2,n+1)/scale)
    return CellRegion(frame=GeometryFrame(frame_id=frame,unit=unit),x_edges=edges,depth_edges=edges,
        membership=tuple(tuple((i<n/2) if left else True for i in range(n)) for _ in range(n)))


def line(x=.5, *, top=-1,bottom=3, error=0,frame=FRAME):
    return Polyline(frame=frame,vertices=((x,top),(x,bottom)),approximation_error_m=error)


@pytest.mark.parametrize('resolution',[2,4,8,32])
def test_analytic_segment_length_and_grid_refinement(resolution):
    target=region(resolution)
    result=curve_region(line(),target,predicate='penetrates')
    assert result.status=='present'
    assert result.interior_length_m==pytest.approx(2)
    assert result.grid_spacing_m==(2/resolution,2/resolution)
    # Inside a union, artificial edges shared by occupied cells are not boundaries.
    assert curve_region(line(x=.5),region(4),predicate='penetrates').status=='present'


def test_boundary_contact_is_not_well_penetration_and_no_hit_is_absent():
    target=region()
    assert curve_region(line(x=1),target).status=='present'
    touching=curve_region(line(x=1),target,predicate='penetrates')
    assert touching.status=='absent' and touching.boundary_touch and touching.interior_length_m==0
    assert curve_region(line(x=1.1),target).status=='absent'
    diagonal=Polyline(frame=FRAME,vertices=((-1,-1),(0,0)))
    assert curve_region(diagonal,target).status=='present'
    assert curve_region(diagonal,target,predicate='penetrates').status=='absent'


def test_tolerance_and_approximation_band_abstain_not_fabricate():
    assert curve_region(line(x=1.000001),region()).status=='absent'
    assert curve_region(line(x=1.000001),region(),tolerance_m=.00001).status=='indeterminate'
    assert curve_region(line(x=.25,error=.5),region(),predicate='penetrates').status=='indeterminate'
    assert curve_region(line(x=.5,error=.1),region(),predicate='penetrates').status=='present'
    with pytest.raises(ValueError):
        curve_region(line(),region(),tolerance_m=float('nan'))


def test_frame_unit_conversion_and_translation_metamorphism():
    original=curve_region(line(),region(),predicate='penetrates')
    km=line(x=.0005,top=-.001,bottom=.003,frame=GeometryFrame(frame_id=FRAME.frame_id,unit='km'))
    assert curve_region(km,region(),predicate='penetrates').interior_length_m==pytest.approx(original.interior_length_m)
    assert contained_by(region(4,unit='km'),region(2,left=False)).status=='present'
    translated=CellRegion(frame=FRAME,x_edges=(10,11,12),depth_edges=(20,21,22),membership=region().membership)
    moved=Polyline(frame=FRAME,vertices=((10.5,19),(10.5,23)))
    assert curve_region(moved,translated,predicate='penetrates').interior_length_m==original.interior_length_m
    assert curve_region(line(frame=GeometryFrame(frame_id='frame:other')),region()).status=='indeterminate'


def test_containment_across_resolutions_absence_and_empty_support():
    assert contained_by(region(8),region(2,left=False)).status=='present'
    assert contained_by(region(2,left=False),region(8)).status=='absent'
    assert contained_by(region(2,left=False),region(8),tolerance_m=.1).status=='indeterminate'
    empty=CellRegion(frame=FRAME,x_edges=(0,1),depth_edges=(0,1),membership=((False,),))
    assert contained_by(empty,region()).status=='indeterminate'


def test_invalid_geometry_contracts_fail_closed():
    for change in [{'membership':((1,False),(True,False))},{'x_edges':(0,2,1)},
                   {'x_edges':(0,1,3)},{'depth_edges':(0,float('inf'),2)}, {'unknown':True}]:
        with pytest.raises(ValidationError):
            CellRegion.model_validate({**region().model_dump(),**change})
    with pytest.raises(ValidationError):
        GeometryFrame(frame_id='f',unit='seconds')
    with pytest.raises(ValidationError):
        GeometryFrame(frame_id='f',axes='xyz')
    with pytest.raises(ValidationError):
        Polyline(frame=FRAME,vertices=((0,0),(0,0)))
    with pytest.raises(ValidationError):
        CellRegion(frame=FRAME,x_edges=(-1e308,1e308),depth_edges=(0,1),membership=((True,),))


def test_bounded_reference_runtime_rejects_pathological_curve_work():
    target=region(64,left=False)
    vertices=tuple((0.,0.) if index%2==0 else (2.,2.) for index in range(600))
    with pytest.raises(ValueError,match='budget'):
        curve_region(Polyline(frame=FRAME,vertices=vertices),target)


@pytest.mark.parametrize('dip,direction',[(85,'positive_x'),(45,'negative_x'),(75,'positive_x')])
def test_supported_fault_definitions_and_grid_resolution(dip,direction):
    def changed(raw):
        raw['structural']['structures'][1].update(dip_deg=dip,dip_direction=direction)
        raw['structural']['grid'].update(nx=80,ndepth=60,dx_m=20,ddepth_m=10)
    inputs,structural,world=bootstrap(changed)
    fault=next(obj for obj in structural_objects(structural) if obj.role=='fault')
    assert isinstance(fault.geometry,Polyline)
    assert ('fault:fault_f1','geoscience:intersects','reservoir-region:r1') in triples(world)
    assert len(world.entities)==len(structural.world.entities)+2


def test_native_fault_admission_remains_bounded():
    # The public structural contract excludes vertical/near-horizontal faults;
    # mathematical vertical polylines remain supported by the geometry layer.
    def vertical(raw):
        raw['structural']['structures'][1]['dip_deg']=90
    with pytest.raises(ValidationError,match='dip_deg'):
        bootstrap(vertical)


def test_registered_reference_protocol_conformance_and_immutability():
    query=GeometryQuery(source=line(),target=region(),predicate='penetrates')
    dataset=xr.Dataset({'geometry_query_json':xr.DataArray(query.model_dump_json(),attrs={'units':'1'})})
    before=dataset.copy(deep=True)
    plugin=SpatialPredicateCapability();registry=CapabilityRegistry();registry.register(plugin)
    report=check_capability(plugin,dataset)
    assert report.conforms,report.issues
    result=registry.execute(plugin.spec.capability_id,plugin.spec.version,dataset)
    assert json.loads(result.dataset['spatial_assessment_json'].item())['status']=='present'
    xr.testing.assert_identical(before,dataset)
    invalid=dataset.copy(deep=True);invalid['geometry_query_json'].attrs['units']='m'
    assert not check_capability(plugin,invalid).conforms
    invalid=xr.Dataset({'geometry_query_json':(('sample',),[query.model_dump_json()],{'units':'1'})})
    assert not check_capability(plugin,invalid).conforms


def bootstrap(payload=None):
    spec=load_flagship_spec(EXAMPLE)
    if payload:
        raw=spec.model_dump(mode='python');payload(raw)
        spec=type(spec).model_validate(raw)
    inputs=compile_flagship_input(spec)
    structural=run_compiled_structural_world(inputs.structural)
    world,_=bootstrap_flagship_semantics(structural,inputs)
    return inputs,structural,world


def triples(world):
    return {(r.source_entity_id,r.relation_type,r.target_entity_id) for r in world.relations}


def test_flagship_claims_change_with_fault_geometry_not_side_masks():
    def outside(raw):
        # Anchor remains inside the valid grid, but the shallowly dipping trace
        # stays entirely below the reservoir's 150–330 m source interval.
        fault=raw['structural']['structures'][1]
        fault.update(x_position_m=0,reference_depth_m=599,dip_deg=5,
                     dip_direction='negative_x',displaced_side='negative_x')
    inputs,structural,world=bootstrap(outside)
    # The reservoir interval is on the selected side; the trace is not there.
    assert structural.dataset['fault_selection'].isel(depth=slice(0,80)).values.all()
    assert not any(r.source_entity_id=='fault:fault_f1' and r.relation_type=='geoscience:intersects' for r in world.relations)
    result=flagship_relationships(world,structural,inputs)
    assert {a.spatial.status for a in result.assessments if a.source_entity_id=='fault:fault_f1'}=={'absent'}


def test_shallow_well_and_multiple_reservoir_formations_remove_claims():
    def shallow(raw):
        raw['well']['bottom_depth_m']=50
        raw['observation']['sample_depths_m']=(25,)
    _,_,world=bootstrap(shallow)
    assert not any(r.source_entity_id=='well:w1' and r.relation_type=='geoscience:penetrates' for r in world.relations)
    def extended(raw):
        raw['structural']['layers'][0]['is_reservoir']=True
    _,_,world=bootstrap(extended)
    assert ('reservoir-region:r1','geoscience:part_of','formation:reservoir_sand') not in triples(world)


def test_repeated_application_is_idempotent_content_bound_and_immutable():
    inputs,structural,world=bootstrap()
    before=world.model_dump_json();original_arrays=structural.dataset.copy(deep=True)
    result=flagship_relationships(world,structural,inputs)
    assert result.world.model_dump_json()==before==world.model_dump_json()
    assert sha256(result.evidence_bytes).hexdigest()==result.representation.content_sha256
    assert check_world(result.world).conforms
    xr.testing.assert_identical(original_arrays,structural.dataset)
    for relation in result.world.relations:
        if relation.relation_id.startswith('relation:flagship'):
            record=next(p for p in result.world.provenance if p.provenance_id in relation.provenance_ids)
            assert result.representation.ref in record.outputs
    assert flagship_relationships(world,structural,inputs).evidence_bytes==result.evidence_bytes


def test_reference_capability_works_outside_flagship_and_unknown_surfaces_abstain():
    inputs,structural,world=bootstrap()
    objects=structural_objects(structural)
    before=structural.world.model_dump_json()
    result=derive_relationships(structural.world,structural.final_state_id,objects)
    assert structural.world.model_dump_json()==before and check_world(result.world).conforms
    assert any(r.source_entity_id=='fault:fault_f1' and r.target_entity_id=='formation:upper_shale' for r in result.world.relations)
    # A later deformation cannot be interpreted as an advected fault surface.
    def later_fold(raw):
        fold=raw['structural']['structures'][0].copy();fold['id']='later_fold'
        raw['structural']['structures'].append(fold)
    inputs,structural,world=bootstrap(later_fold)
    fault=next(obj for obj in structural_objects(structural) if obj.role=='fault')
    assert isinstance(fault.geometry,UnknownGeometry)
    assert {a.spatial.status for a in flagship_relationships(world,structural,inputs).assessments if a.source_entity_id.startswith('fault:')}=={'indeterminate'}


def test_geometry_alone_never_assigns_part_of_and_false_roles_rejected():
    inputs,structural,world=bootstrap()
    base=next(obj for obj in structural_objects(structural) if obj.entity_id=='formation:reservoir_sand')
    region_obj=SpatialObject(entity_id='reservoir-region:r1',role='region',geometry=base.geometry,evidence=base.evidence)
    result=derive_relationships(world,structural.final_state_id,(base,region_obj))
    assert not result.assessments  # no authored geological membership context
    with pytest.raises(ValueError,match='roles'):
        derive_relationships(world,structural.final_state_id,(base.model_copy(update={'role':'well'}),))


def test_geometry_adapter_rejects_changed_compiled_input():
    from dataclasses import replace
    _,structural,_=bootstrap()
    changed=structural.structural_input.model_copy(update={'root_seed':999})
    with pytest.raises(ValueError,match='World-bound input'):
        structural_objects(replace(structural,structural_input=changed))
