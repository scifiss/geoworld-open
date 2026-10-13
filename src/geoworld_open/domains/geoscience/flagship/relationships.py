"""Compatibility adapter: explicit flagship objects, reusable spatial assessment."""
from geoworld_open.domains.geoscience.relationships import SpatialObject, derive_relationships
from geoworld_open.domains.geoscience.structural.relationships import structural_objects
from geoworld_open.reference.spatial import CellRegion, Polyline


def flagship_relationships(world, structural_result, inputs):
    formation_id='formation:'+inputs.reservoir_region.formation_id
    fault_id='fault:'+inputs.reservoir_region.intersecting_fault_id
    objects=[obj for obj in structural_objects(structural_result) if obj.entity_id in {formation_id,fault_id}]
    # Read the declared cell selection unchanged, including any support mismatch.
    template=next(obj.geometry for obj in objects if obj.entity_id==formation_id)
    mask=structural_result.stratigraphy_bundle.to_dataset()['reservoir_selection'].values
    region=CellRegion(frame=template.frame,x_edges=template.x_edges,depth_edges=template.depth_edges,
        membership=tuple(tuple(bool(value) for value in row) for row in mask))
    objects.append(SpatialObject(entity_id='reservoir-region:'+inputs.reservoir_region.id,role='region',geometry=region,
        evidence=(structural_result.stratigraphy_bundle.representation.ref,),part_of_target_id=formation_id))
    trajectory=next(rep for rep in world.representations if rep.representation_id=='representation:flagship-well-trajectory')
    objects.append(SpatialObject(entity_id='well:'+inputs.well.id,role='well',
        geometry=Polyline(frame=template.frame,vertices=((inputs.well.x_m,inputs.well.top_depth_m),(inputs.well.x_m,inputs.well.bottom_depth_m))),
        evidence=(trajectory.ref,)))
    roles={obj.entity_id:obj.role for obj in objects}
    def compatibility_id(source,relation,target):
        # IDs only, never presence assertions. Preserve the old five ID spellings.
        return 'relation:flagship-'+roles[source]+'-'+relation.split(':')[-1].replace('_','-')+'-'+roles[target]
    return derive_relationships(world,structural_result.final_state_id,tuple(objects),relation_id=compatibility_id)
