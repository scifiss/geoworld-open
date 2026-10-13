"""Bounded 2-D predicates on explicit cell unions and piecewise-linear curves.

No entity types or scientific relation meanings are inferred here.
"""
from __future__ import annotations

from math import hypot
from typing import Literal, Annotated
import numpy as np
from pydantic import Field, StrictBool, model_validator
from geoworld_open.standard.capabilities import ContractModel
from geoworld_open.world.models import Identifier, NonEmptyStr


class GeometryFrame(ContractModel):
    frame_id: Identifier
    unit: Literal['m', 'km'] = 'm'
    axes: Literal['x_depth_positive_down'] = 'x_depth_positive_down'

    @property
    def factor(self):
        return 1000. if self.unit == 'km' else 1.


class CellRegion(ContractModel):
    kind: Literal['cell_region'] = 'cell_region'
    frame: GeometryFrame
    x_edges: tuple[float, ...] = Field(min_length=2, max_length=1025)
    depth_edges: tuple[float, ...] = Field(min_length=2, max_length=1025)
    membership: tuple[tuple[StrictBool, ...], ...]

    @model_validator(mode='after')
    def grid(self):
        for edges in (self.x_edges, self.depth_edges):
            with np.errstate(over='ignore'):
                steps=np.diff(np.asarray(edges)*self.frame.factor)
            if not np.isfinite(steps).all() or np.any(steps<=0) or not np.allclose(steps,steps[0],rtol=1e-12,atol=0):
                raise ValueError('cell regions require increasing regular grid edges')
        if len(self.membership)!=len(self.depth_edges)-1 or any(len(row)!=len(self.x_edges)-1 for row in self.membership):
            raise ValueError('membership shape must match depth/x cell support')
        if (len(self.depth_edges)-1)*(len(self.x_edges)-1)>131072:
            raise ValueError('reference geometry exceeds the bounded cell budget')
        return self

    def arrays_m(self):
        return np.array(self.x_edges)*self.frame.factor, np.array(self.depth_edges)*self.frame.factor, np.array(self.membership,dtype=bool)


class Polyline(ContractModel):
    kind: Literal['polyline'] = 'polyline'
    frame: GeometryFrame
    vertices: tuple[tuple[float,float], ...] = Field(min_length=2,max_length=4097)
    approximation_error_m: float = Field(default=0,ge=0)

    @model_validator(mode='after')
    def length(self):
        with np.errstate(over='ignore'):
            converted=np.array(self.vertices)*self.frame.factor
        increments=np.diff(converted,axis=0)
        lengths=[hypot(*delta) for delta in increments]
        if not np.isfinite(converted).all() or not np.isfinite(increments).all() or not np.isfinite(sum(lengths)):
            raise ValueError('curve coordinates and increments must be finite in metres')
        if all(a==b for a,b in zip(self.vertices,self.vertices[1:])):
            raise ValueError('curve must have nonzero length')
        return self


class UnknownGeometry(ContractModel):
    kind: Literal['unknown'] = 'unknown'
    frame: GeometryFrame
    reason: NonEmptyStr


Geometry = Annotated[CellRegion | Polyline | UnknownGeometry, Field(discriminator='kind')]


class GeometryQuery(ContractModel):
    source: Geometry
    target: Geometry
    predicate: Literal['contained_by','intersects','penetrates']
    tolerance_m: float = Field(default=0,ge=0)


class SpatialAssessment(ContractModel):
    predicate: Literal['contained_by', 'intersects', 'penetrates']
    status: Literal['present', 'absent', 'indeterminate']
    reason: NonEmptyStr
    interior_length_m: float = Field(default=0,ge=0)
    boundary_touch: bool = False
    tolerance_m: float = Field(default=0,ge=0)
    grid_spacing_m: tuple[float,float] | None = None


def _candidate_cells(edges, low, high):
    start=max(0,int(np.searchsorted(edges,low,side='left'))-1)
    stop=min(len(edges)-1,int(np.searchsorted(edges,high,side='right')))
    return range(start,stop)


def _clip(a,b,rect):
    """Closed rectangle slab clipping in parametric segment coordinates."""
    lo,hi=0.,1.
    for axis,(lower,upper) in enumerate(((rect[0],rect[1]),(rect[2],rect[3]))):
        delta=b[axis]-a[axis]
        if delta==0:
            if not lower<=a[axis]<=upper:
                return None
        else:
            u,v=(lower-a[axis])/delta,(upper-a[axis])/delta
            lo=max(lo,min(u,v));hi=min(hi,max(u,v))
            if hi<lo:
                return None
    return lo,hi


def _interior(x,z,mask,point,radius):
    """An entire uncertainty square must lie in the cell union.

    Adjacent occupied cells remove artificial grid seams from the interior.
    """
    px,pz=point
    if not (x[0]<px-radius and px+radius<x[-1] and z[0]<pz-radius and pz+radius<z[-1]):
        return False
    return all(mask[j,i] for i in _candidate_cells(x,px-radius,px+radius)
               for j in _candidate_cells(z,pz-radius,pz+radius))


def curve_region(curve: Polyline, region: CellRegion, *, predicate='intersects', tolerance_m=0.) -> SpatialAssessment:
    if predicate not in {'intersects','penetrates'} or not np.isfinite(tolerance_m) or tolerance_m<0:
        raise ValueError('invalid curve predicate or tolerance')
    spacing=(float((region.x_edges[1]-region.x_edges[0])*region.frame.factor),
             float((region.depth_edges[1]-region.depth_edges[0])*region.frame.factor))
    def result(status,reason,**values):
        return SpatialAssessment(predicate=predicate,status=status,reason=reason,tolerance_m=tolerance_m,grid_spacing_m=spacing,**values)
    if curve.frame.frame_id!=region.frame.frame_id or curve.frame.axes!=region.frame.axes:
        return result('indeterminate','Coordinate frames are incompatible; no implicit transformation is available.')
    x,z,mask=region.arrays_m()
    points=np.array(curve.vertices)*curve.frame.factor
    radius=curve.approximation_error_m+tolerance_m
    if not np.isfinite(radius):
        raise ValueError('combined uncertainty must be finite')
    # Admit the entire query's work before visiting any cells.
    planned_visits=sum(len(_candidate_cells(x,min(a[0],b[0])-radius,max(a[0],b[0])+radius))*
                       len(_candidate_cells(z,min(a[1],b[1])-radius,max(a[1],b[1])+radius))
                       for a,b in zip(points,points[1:]))
    if planned_visits>2_000_000:
        raise ValueError('curve/region query exceeds the bounded cell-visit budget')
    interior=0.;nominal=False;possible=False;boundary=False;robust=False;visits=0
    for a,b in zip(points,points[1:]):
        length=hypot(*(b-a))
        if not length:
            continue
        intervals=[]
        ix=_candidate_cells(x,min(a[0],b[0])-radius,max(a[0],b[0])+radius)
        iz=_candidate_cells(z,min(a[1],b[1])-radius,max(a[1],b[1])+radius)
        visits+=len(ix)*len(iz)
        if visits>2_000_000:
            raise ValueError('curve/region query exceeds the bounded cell-visit budget')
        for i in ix:
            for j in iz:
                if not mask[j,i]:
                    continue
                rect=(x[i],x[i+1],z[j],z[j+1])
                if _clip(a,b,(rect[0]-radius,rect[1]+radius,rect[2]-radius,rect[3]+radius)) is not None:
                    possible=True
                interval=_clip(a,b,rect)
                if interval is not None:
                    nominal=True;intervals.append(interval)
        cuts=sorted({value for interval in intervals for value in interval})
        for lo,hi in zip(cuts,cuts[1:]):
            mid=a+(b-a)*((lo+hi)/2)
            if not any(start<((lo+hi)/2)<end for start,end in intervals):
                continue
            if _interior(x,z,mask,mid,0.):
                interior+=(hi-lo)*length
                robust |= _interior(x,z,mask,mid,radius)
            else:
                boundary=True
        for start,end in intervals:
            if start==end or not _interior(x,z,mask,a+(b-a)*start,0.):
                boundary=True
    values={'interior_length_m':interior,'boundary_touch':boundary}
    if robust or (predicate=='intersects' and nominal and radius==0):
        return result('present','Intersection justified on the declared cell-union support.',**values)
    if predicate=='penetrates' and nominal and not interior and radius==0:
        return result('absent','Boundary contact alone is not penetration.',**values)
    if possible:
        return result('indeterminate','Only boundary/approximation-band contact; interior penetration is not established.',**values)
    return result('absent','No intersection even within the declared tolerance/approximation band.',**values)


def contained_by(child: CellRegion, parent: CellRegion, *, tolerance_m=0.) -> SpatialAssessment:
    if not np.isfinite(tolerance_m) or tolerance_m<0:
        raise ValueError('invalid tolerance')
    def result(status,reason):
        return SpatialAssessment(predicate='contained_by',status=status,reason=reason,tolerance_m=tolerance_m,
            grid_spacing_m=((child.x_edges[1]-child.x_edges[0])*child.frame.factor,(child.depth_edges[1]-child.depth_edges[0])*child.frame.factor))
    if child.frame.frame_id!=parent.frame.frame_id:
        return result('indeterminate','Coordinate frames are incompatible.')
    x,z,mask=child.arrays_m();px,pz,pm=parent.arrays_m()
    if not np.any(mask):
        return result('indeterminate','An empty child footprint cannot establish a scientific part-of relation.')
    if np.array_equal(x,px) and np.array_equal(z,pz):
        supported=not np.any(mask & ~pm)
    else:
        supported=True
        visits=0
        for j,i in zip(*np.nonzero(mask)):
            area=(x[i+1]-x[i])*(z[j+1]-z[j]);covered=0.
            if not np.isfinite(area) or area==0:
                raise ValueError('cell area must be finite and representable')
            ix=_candidate_cells(px,x[i],x[i+1]);iz=_candidate_cells(pz,z[j],z[j+1])
            visits+=len(ix)*len(iz)
            if visits>2_000_000:
                raise ValueError('containment query exceeds the bounded cell-visit budget')
            for pi in ix:
                for pj in iz:
                    if pm[pj,pi]:
                        covered+=max(0,min(x[i+1],px[pi+1])-max(x[i],px[pi]))*max(0,min(z[j+1],pz[pj+1])-max(z[j],pz[pj]))
            if not np.isclose(covered,area,rtol=1e-12,atol=0):
                supported=False;break
    if supported:
        return result('present','Nonempty cell-union footprint is contained by the declared parent footprint.')
    if tolerance_m:
        return result('indeterminate','Containment fails; a nonzero boundary tolerance must not fabricate part-of semantics.')
    return result('absent','Some child area lies outside the parent footprint.')


def evaluate_query(query: GeometryQuery) -> SpatialAssessment:
    query=GeometryQuery.model_validate(query)
    if isinstance(query.source,UnknownGeometry) or isinstance(query.target,UnknownGeometry):
        return SpatialAssessment(predicate=query.predicate,status='indeterminate',reason='Explicit geometry is unavailable.',tolerance_m=query.tolerance_m)
    if query.predicate=='contained_by' and isinstance(query.source,CellRegion) and isinstance(query.target,CellRegion):
        return contained_by(query.source,query.target,tolerance_m=query.tolerance_m)
    if query.predicate in {'intersects','penetrates'} and isinstance(query.source,Polyline) and isinstance(query.target,CellRegion):
        return curve_region(query.source,query.target,predicate=query.predicate,tolerance_m=query.tolerance_m)
    return SpatialAssessment(predicate=query.predicate,status='indeterminate',reason='This geometry pair is outside the reference validity domain.',tolerance_m=query.tolerance_m)


class SpatialPredicateCapability:
    """Scalar JSON transport through the existing xarray plugin contract.

    The payload itself is the strict GeometryQuery contract. World roles and
    provenance-backed semantic assignment remain a separate domain adapter.
    """
    from geoworld_open.standard.capabilities import CapabilitySpec, CapabilityKind, VariableSpec, ValidityDomain, DTypeKind
    spec=CapabilitySpec(capability_id='reference.spatial_predicates',version='1.0.0',kind=CapabilityKind.GEOMETRY,
        title='Closed cell-union containment and piecewise-linear curve intersection',law_name='2D rectangle clipping',
        inputs=(VariableSpec(name='geometry_query_json',unit='1',dtype_kind=DTypeKind.STRING),),
        outputs=(VariableSpec(name='spatial_assessment_json',unit='1',dtype_kind=DTypeKind.STRING),),
        validity_domain=ValidityDomain(description='Explicit bounded 2D regular cell unions and polylines in compatible local length frames.',
            excluded_uses=('3D topology','implicit frame transforms','fault-side masks as surfaces','scientific semantics from geometry alone')),
        assumptions=('Grid membership denotes entire closed cells; subcell geological boundaries are not inferred.',
                     'Nonzero tolerance and curve approximation bounds cannot establish boundary-only scientific claims.'),
        references=('Slab segment clipping against closed rectangles; interval union and rectangular area coverage.',))

    def execute(self,dataset,context):
        import xarray as xr
        from geoworld_open.standard.capabilities import CapabilityRunResult, numpy_dtype_kind
        array=dataset['geometry_query_json']
        if array.dims or array.attrs.get('units')!='1' or numpy_dtype_kind(array.dtype)!=self.DTypeKind.STRING:
            raise ValueError('geometry_query_json requires a scalar string with unit 1')
        query=GeometryQuery.model_validate_json(str(array.item()))
        assessment=evaluate_query(query)
        output=xr.Dataset({'spatial_assessment_json':xr.DataArray(assessment.model_dump_json(),attrs={'units':'1'})})
        return CapabilityRunResult(output,{'method':'cell_union_relationships_v1'})
