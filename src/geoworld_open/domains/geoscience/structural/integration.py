"""Compile structural GeoSpec input into an authoritative semantic World transition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import xarray as xr

from geoworld_open.domains.geoscience.structural.capabilities import (
    structural_capabilities,
)
from geoworld_open.domains.geoscience.structural.numerics import create_structural_grid
from geoworld_open.engine import ExecutionContext, ExecutionPlan, SeedManager, compile_plan
from geoworld_open.specs import FaultSpec, FoldSpec, GeoSpec
from geoworld_open.world import (
    Directionality,
    Entity,
    FieldBinding,
    FieldDefinition,
    FrameScope,
    Missingness,
    PhysicalRank,
    PositiveDirection,
    Provenance,
    ReferenceFrame,
    Relation,
    SubjectKind,
    SubjectRef,
    Support,
    SupportKind,
    TransitionResult,
    ValueKind,
    World,
    WorldOrigin,
    WorldState,
    WorldStateRole,
    XarrayBundle,
    apply_transition,
    create_xarray_bundle,
)


INITIAL_STATE_ID = "state:structural-initial"
FINAL_STATE_ID = "state:structural-final"
FRAME_ID = "frame:structural-depth-x"
SUPPORT_ID = "support:structural-grid"
ROOT_ENTITY_ID = "model:structural-earth"

GEOMETRY_VARIABLES = (
    "source_depth_m",
    "structural_displacement_m",
    "fold_displacement_m",
    "fault_displacement_m",
    "fault_selection",
    "boundary_clipped_mask",
)
STRATIGRAPHIC_VARIABLES = (
    "layer_index",
    "facies",
    "porosity",
    "reservoir_selection",
)


@dataclass(frozen=True)
class NumericalExecution:
    dataset: xr.Dataset
    fragments: dict[str, xr.Dataset]
    diagnostics: dict[str, dict[str, Any]]
    trace: tuple[dict[str, Any], ...]
    seed_lineage: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class StructuralWorldResult:
    """Validated semantic and numerical result of one structural World run."""

    spec: GeoSpec
    initial_world: World
    world: World
    plan: ExecutionPlan
    numerical: NumericalExecution
    geometry_bundle: XarrayBundle
    stratigraphy_bundle: XarrayBundle

    @property
    def initial_state_id(self) -> str:
        return INITIAL_STATE_ID

    @property
    def final_state_id(self) -> str:
        return FINAL_STATE_ID

    @property
    def dataset(self) -> xr.Dataset:
        return self.numerical.dataset.copy(deep=True)


def _entity_ref(entity_id: str) -> SubjectRef:
    return SubjectRef(kind=SubjectKind.ENTITY, subject_id=entity_id)


def _state_ref(state_id: str) -> SubjectRef:
    return SubjectRef(kind=SubjectKind.WORLD_STATE, subject_id=state_id)


def _binding_ref(binding_id: str) -> SubjectRef:
    return SubjectRef(kind=SubjectKind.FIELD_BINDING, subject_id=binding_id)


def _field_definition(
    name: str,
    *,
    unit: str,
    value_kind: ValueKind,
    classification: str,
) -> FieldDefinition:
    return FieldDefinition(
        field_id=f"field:{name}",
        canonical_name=name,
        unit=unit,
        value_kind=value_kind,
        physical_rank=PhysicalRank.SCALAR,
        missingness=Missingness.FORBID,
        admissible_support_kinds=(SupportKind.REGULAR_GRID,),
        domain_constraint_refs=(f"geoscience:field_class:{classification}",),
        provenance_ids=("provenance:structural-bootstrap",),
    )


def _structural_field_definitions() -> tuple[FieldDefinition, ...]:
    return (
        _field_definition(
            "source_depth_m", unit="m", value_kind=ValueKind.CONTINUOUS,
            classification="computational",
        ),
        _field_definition(
            "structural_displacement_m", unit="m", value_kind=ValueKind.CONTINUOUS,
            classification="derived_scientific",
        ),
        _field_definition(
            "fold_displacement_m", unit="m", value_kind=ValueKind.CONTINUOUS,
            classification="derived_scientific",
        ),
        _field_definition(
            "fault_displacement_m", unit="m", value_kind=ValueKind.CONTINUOUS,
            classification="derived_scientific",
        ),
        _field_definition(
            "fault_selection", unit="1", value_kind=ValueKind.BOOLEAN,
            classification="derived_scientific",
        ),
        _field_definition(
            "boundary_clipped_mask", unit="1", value_kind=ValueKind.BOOLEAN,
            classification="diagnostic",
        ),
        _field_definition(
            "layer_index", unit="1", value_kind=ValueKind.DISCRETE,
            classification="computational",
        ),
        _field_definition(
            "facies", unit="1", value_kind=ValueKind.CATEGORICAL,
            classification="scientific_state",
        ),
        _field_definition(
            "porosity", unit="1", value_kind=ValueKind.CONTINUOUS,
            classification="scientific_state",
        ),
        _field_definition(
            "reservoir_selection", unit="1", value_kind=ValueKind.BOOLEAN,
            classification="derived_scientific",
        ),
    )


def bootstrap_structural_world(spec: GeoSpec) -> World:
    """Compile authoring input into semantic identities and one empty initial state."""
    bootstrap_id = "provenance:structural-bootstrap"
    entities: list[Entity] = [
        Entity(
            entity_id=ROOT_ENTITY_ID,
            entity_type="geoscience:structural_model",
            label=spec.metadata.name,
            provenance_ids=(bootstrap_id,),
        )
    ]
    relations: list[Relation] = []

    for index, formation in enumerate(spec.layers):
        entity_id = f"formation:{formation.id}"
        entities.append(
            Entity(
                entity_id=entity_id,
                entity_type="geoscience:formation",
                label=formation.name,
                provenance_ids=(bootstrap_id,),
            )
        )
        relations.append(
            Relation(
                relation_id=f"relation:{formation.id}:part-of-model",
                source_entity_id=entity_id,
                relation_type="geoscience:part_of",
                target_entity_id=ROOT_ENTITY_ID,
                qualifiers=(
                    ("stratigraphic_order", index),
                    ("facies_id", formation.facies_id),
                    ("reservoir_role", formation.is_reservoir),
                ),
                provenance_ids=(bootstrap_id,),
            )
        )
        if index:
            relations.append(
                Relation(
                    relation_id=f"relation:{spec.layers[index - 1].id}:overlies:{formation.id}",
                    source_entity_id=f"formation:{spec.layers[index - 1].id}",
                    relation_type="geoscience:overlies",
                    target_entity_id=entity_id,
                    provenance_ids=(bootstrap_id,),
                )
            )

    for structure in spec.structures:
        if isinstance(structure, FaultSpec):
            entity_type = "geoscience:fault"
            entity_id = f"fault:{structure.id}"
        else:
            assert isinstance(structure, FoldSpec)
            entity_type = "geoscience:fold"
            entity_id = f"fold:{structure.id}"
        entities.append(
            Entity(
                entity_id=entity_id,
                entity_type=entity_type,
                label=structure.id.replace("_", " ").title(),
                provenance_ids=(bootstrap_id,),
            )
        )
        relations.append(
            Relation(
                relation_id=f"relation:{structure.id}:deforms-model",
                source_entity_id=entity_id,
                relation_type="geoscience:deforms",
                target_entity_id=ROOT_ENTITY_ID,
                directionality=Directionality.DIRECTED,
                qualifiers=(("operation_order", spec.structures.index(structure)),),
                provenance_ids=(bootstrap_id,),
            )
        )

    frame = ReferenceFrame(
        frame_id=FRAME_ID,
        label="cell-centered structural depth section",
        scope=FrameScope.LOCAL,
        coordinate_names=("depth", "x"),
        units=("m", "m"),
        positive_directions=(PositiveDirection.DOWN, PositiveDirection.INCREASING),
        provenance_ids=(bootstrap_id,),
    )
    support = Support(
        support_id=SUPPORT_ID,
        support_kind=SupportKind.REGULAR_GRID,
        dimension_names=("depth", "x"),
        shape=(spec.grid.ndepth, spec.grid.nx),
        reference_frame_id=FRAME_ID,
        provenance_ids=(bootstrap_id,),
    )
    definitions = _structural_field_definitions()
    initial_state = WorldState(
        state_id=INITIAL_STATE_ID,
        world_id=f"world:{spec.metadata.name}",
        role=WorldStateRole.HYPOTHETICAL,
        provenance_ids=(bootstrap_id,),
    )

    bootstrap_outputs = (
        *(_entity_ref(entity.entity_id) for entity in entities),
        *(
            SubjectRef(kind=SubjectKind.RELATION, subject_id=relation.relation_id)
            for relation in relations
        ),
        *(
            SubjectRef(kind=SubjectKind.FIELD_DEFINITION, subject_id=item.field_id)
            for item in definitions
        ),
        SubjectRef(kind=SubjectKind.SUPPORT, subject_id=SUPPORT_ID),
        _state_ref(INITIAL_STATE_ID),
    )
    provenance = Provenance(
        provenance_id=bootstrap_id,
        activity_type="geoscience:world_bootstrap",
        method="GeoSpec structural semantic compiler",
        outputs=bootstrap_outputs,
        parameters=(
            ("schema_version", spec.schema_version),
            ("root_seed", spec.seed),
            ("structural_method", spec.structural_method.method_id),
        ),
    )
    return World(
        world_id=initial_state.world_id,
        label=spec.metadata.name,
        origin=WorldOrigin.SYNTHETIC,
        entities=tuple(entities),
        relations=tuple(relations),
        field_definitions=definitions,
        states=(initial_state,),
        provenance=(provenance,),
        reference_frames=(frame,),
        supports=(support,),
        metadata=(("geospec_schema_version", spec.schema_version),),
    )


def _validate_fragment(capability_id: str, fragment: xr.Dataset, plan: ExecutionPlan) -> None:
    capability = next(
        item for item in plan.capabilities if item.metadata.capability_id == capability_id
    )
    contracts = {item.name: item for item in capability.metadata.produces}
    if set(fragment.data_vars) != set(contracts):
        raise ValueError(
            f"capability {capability_id!r} returned variables that differ from its contract"
        )
    for name, contract in contracts.items():
        variable = fragment[name]
        if variable.dims != contract.dims:
            raise ValueError(f"capability {capability_id!r} returned wrong dimensions for {name!r}")
        if variable.attrs.get("units") != contract.units:
            raise ValueError(f"capability {capability_id!r} returned wrong units for {name!r}")
        if contract.dtype_kind and variable.dtype.kind != contract.dtype_kind:
            raise ValueError(f"capability {capability_id!r} returned wrong dtype kind for {name!r}")


def _execute_plan(spec: GeoSpec, plan: ExecutionPlan) -> NumericalExecution:
    dataset = create_structural_grid(spec)
    seed_manager = SeedManager(spec.seed)
    fragments: dict[str, xr.Dataset] = {}
    diagnostics: dict[str, dict[str, Any]] = {}
    lineage: dict[str, dict[str, Any]] = {}
    trace: list[dict[str, Any]] = []

    for capability in plan.capabilities:
        capability_id = capability.metadata.capability_id
        capability_lineage = seed_manager.lineage(capability_id)
        context = ExecutionContext(
            spec=spec,
            capability_id=capability_id,
            rng=seed_manager.generator(capability_id),
            seed_lineage=capability_lineage,
        )
        result = capability.execute(dataset.copy(deep=True), context)
        _validate_fragment(capability_id, result.dataset, plan)
        overlap = set(dataset.data_vars).intersection(result.dataset.data_vars)
        if overlap:
            raise ValueError(f"capability {capability_id!r} overwrote variables: {sorted(overlap)}")
        dataset = xr.merge((dataset, result.dataset), compat="equals", join="exact")
        fragments[capability_id] = result.dataset.copy(deep=True)
        diagnostics[capability_id] = result.diagnostics
        lineage[capability_id] = capability_lineage
        trace.append(
            {
                "capability_id": capability_id,
                "version": capability.metadata.version,
                "method_id": capability.metadata.method_id,
                "inputs": [item.name for item in capability.metadata.requires],
                "outputs": [item.name for item in capability.metadata.produces],
                "deterministic": capability.metadata.deterministic,
                "assumptions": list(capability.metadata.assumptions),
                "references": list(capability.metadata.references),
            }
        )

    return NumericalExecution(
        dataset=dataset,
        fragments=fragments,
        diagnostics=diagnostics,
        trace=tuple(trace),
        seed_lineage=lineage,
    )


def _make_bindings(
    names: tuple[str, ...],
    *,
    representation_id: str,
    provenance_id: str,
) -> dict[str, FieldBinding]:
    representation_ref = SubjectRef(
        kind=SubjectKind.REPRESENTATION,
        subject_id=representation_id,
        representation_version="v1",
    )
    return {
        name: FieldBinding(
            binding_id=f"binding:{name}:structural-final",
            field_definition_id=f"field:{name}",
            subject=SubjectRef(kind=SubjectKind.SUPPORT, subject_id=SUPPORT_ID),
            world_state_id=FINAL_STATE_ID,
            representation=representation_ref,
            support_id=SUPPORT_ID,
            scale_label="structural-grid-cell",
            provenance_ids=(provenance_id,),
        )
        for name in names
    }


class StructuralTransition:
    """Domain transition that maps pure structural arrays into kernel contracts."""

    transition_id = "transition:structural-geology-v1"

    def __init__(self, spec: GeoSpec, plan: ExecutionPlan) -> None:
        self.spec = spec
        self.plan = plan
        self.numerical: NumericalExecution | None = None
        self.geometry_bundle: XarrayBundle | None = None
        self.stratigraphy_bundle: XarrayBundle | None = None

    def apply(self, world: World, input_state: WorldState) -> TransitionResult:
        if input_state.state_id != INITIAL_STATE_ID:
            raise ValueError("StructuralTransition requires the compiled initial state")

        numerical = _execute_plan(self.spec, self.plan)
        geometry_representation_id = "representation:structural-geometry"
        stratigraphy_representation_id = "representation:stratigraphic-fields"
        geometry_provenance_id = "provenance:structural-geometry"
        stratigraphy_provenance_id = "provenance:stratigraphic-assignment"
        transition_provenance_id = "provenance:structural-transition"

        geometry_bindings = _make_bindings(
            GEOMETRY_VARIABLES,
            representation_id=geometry_representation_id,
            provenance_id=geometry_provenance_id,
        )
        stratigraphy_bindings = _make_bindings(
            STRATIGRAPHIC_VARIABLES,
            representation_id=stratigraphy_representation_id,
            provenance_id=stratigraphy_provenance_id,
        )
        geometry_ref = next(iter(geometry_bindings.values())).representation
        stratigraphy_ref = next(iter(stratigraphy_bindings.values())).representation
        final_state = WorldState(
            state_id=FINAL_STATE_ID,
            world_id=world.world_id,
            role=WorldStateRole.SIMULATED,
            parent_state_id=input_state.state_id,
            field_binding_ids=tuple(
                binding.binding_id
                for binding in (*geometry_bindings.values(), *stratigraphy_bindings.values())
            ),
            representation_refs=(geometry_ref, stratigraphy_ref),
            provenance_ids=(transition_provenance_id,),
        )

        structure_refs = tuple(
            _entity_ref(
                f"fault:{item.id}" if isinstance(item, FaultSpec) else f"fold:{item.id}"
            )
            for item in self.spec.structures
        )
        formation_refs = tuple(
            _entity_ref(f"formation:{item.id}") for item in self.spec.layers
        )
        geometry_provenance = Provenance(
            provenance_id=geometry_provenance_id,
            activity_type="geoscience:structural_geometry",
            method="analytic_source_depth_v1",
            inputs=(_state_ref(input_state.state_id), *structure_refs),
            outputs=(
                *(_binding_ref(item.binding_id) for item in geometry_bindings.values()),
                geometry_ref,
            ),
            parameters=(
                ("capability_id", "structural_geometry"),
                ("capability_version", "3.0.0"),
                ("root_seed", self.spec.seed),
                ("operation_order", self.spec.structural_method.operation_order),
            ),
        )
        stratigraphy_provenance = Provenance(
            provenance_id=stratigraphy_provenance_id,
            activity_type="geoscience:stratigraphic_assignment",
            method="explicit_layer_lookup_v1",
            inputs=(_state_ref(input_state.state_id), geometry_ref, *formation_refs),
            outputs=(
                *(_binding_ref(item.binding_id) for item in stratigraphy_bindings.values()),
                stratigraphy_ref,
            ),
            parent_provenance_ids=(geometry_provenance_id,),
            parameters=(
                ("capability_id", "stratigraphic_assignment"),
                ("capability_version", "3.0.0"),
                ("root_seed", self.spec.seed),
            ),
        )
        transition_provenance = Provenance(
            provenance_id=transition_provenance_id,
            activity_type="world:state_transition",
            method=self.transition_id,
            inputs=(_state_ref(input_state.state_id), geometry_ref, stratigraphy_ref),
            outputs=(_state_ref(final_state.state_id),),
            parent_provenance_ids=(geometry_provenance_id, stratigraphy_provenance_id),
            parameters=(("root_seed", self.spec.seed),),
        )

        support = world.supports[0]
        frame = world.reference_frames[0]
        geometry_bundle = create_xarray_bundle(
            numerical.fragments["structural_geometry"],
            world_id=world.world_id,
            state=final_state,
            support=support,
            reference_frame=frame,
            representation_id=geometry_representation_id,
            version="v1",
            variable_bindings=geometry_bindings,
            field_definitions=world.field_definitions,
            provenance=geometry_provenance,
        )
        stratigraphy_bundle = create_xarray_bundle(
            numerical.fragments["stratigraphic_assignment"],
            world_id=world.world_id,
            state=final_state,
            support=support,
            reference_frame=frame,
            representation_id=stratigraphy_representation_id,
            version="v1",
            variable_bindings=stratigraphy_bindings,
            field_definitions=world.field_definitions,
            provenance=stratigraphy_provenance,
            derived_from=(geometry_bundle.representation.ref,),
        )

        self.numerical = numerical
        self.geometry_bundle = geometry_bundle
        self.stratigraphy_bundle = stratigraphy_bundle
        return TransitionResult(
            state=final_state,
            field_bindings=tuple((*geometry_bindings.values(), *stratigraphy_bindings.values())),
            representations=(
                geometry_bundle.representation,
                stratigraphy_bundle.representation,
            ),
            provenance=(
                geometry_provenance,
                stratigraphy_provenance,
                transition_provenance,
            ),
        )


def run_structural_world(spec: GeoSpec) -> StructuralWorldResult:
    """Run structural science through the semantic World transition boundary."""
    initial_world = bootstrap_structural_world(spec)
    plan = compile_plan(structural_capabilities())
    transition = StructuralTransition(spec, plan)
    execution = apply_transition(initial_world, INITIAL_STATE_ID, transition)
    if (
        transition.numerical is None
        or transition.geometry_bundle is None
        or transition.stratigraphy_bundle is None
    ):
        raise RuntimeError("structural transition completed without numerical bundles")
    return StructuralWorldResult(
        spec=spec,
        initial_world=initial_world,
        world=execution.world,
        plan=plan,
        numerical=transition.numerical,
        geometry_bundle=transition.geometry_bundle,
        stratigraphy_bundle=transition.stratigraphy_bundle,
    )
