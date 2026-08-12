"""Flagship semantic enrichment, transparent state changes, and observation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import xarray as xr

from geoworld_open.domains.geoscience.flagship.input import (
    CompiledFlagshipInput,
    FlagshipSpec,
    canonical_flagship_input_bytes,
    compile_flagship_input,
    flagship_input_sha256,
)
from geoworld_open.domains.geoscience.flagship.numerics import (
    PressureObservationRow,
    compute_baseline_fields,
    compute_perturbed_pressure_fields,
    observation_csv_bytes,
    sample_well_pressure,
    well_trajectory_csv_bytes,
)
from geoworld_open.domains.geoscience.structural import (
    StructuralWorldResult,
    run_compiled_structural_world,
    structural_input_sha256,
)
from geoworld_open.domains.geoscience.structural.integration import (
    FINAL_STATE_ID as STRUCTURAL_STATE_ID,
    INPUT_REPRESENTATION_ID as STRUCTURAL_INPUT_REPRESENTATION_ID,
    INPUT_REPRESENTATION_VERSION as STRUCTURAL_INPUT_REPRESENTATION_VERSION,
    ROOT_ENTITY_ID,
    SUPPORT_ID,
)
from geoworld_open.world import (
    Entity,
    FieldBinding,
    FieldDefinition,
    Missingness,
    Observation,
    ObservationStatus,
    PhysicalRank,
    Provenance,
    Relation,
    Representation,
    RepresentationKind,
    SubjectKind,
    SubjectRef,
    Support,
    SupportKind,
    TemporalValue,
    TransitionResult,
    ValueKind,
    World,
    WorldState,
    WorldStateRole,
    XarrayBundle,
    apply_transition,
    create_xarray_bundle,
)


FLAGSHIP_INPUT_REPRESENTATION_ID = "representation:flagship-input"
FLAGSHIP_INPUT_REPRESENTATION_VERSION = "v1"
FLAGSHIP_INPUT_ARTIFACT_URI = "artifact://inputs/flagship-input.json"
BASELINE_STATE_ID = "state:flagship-baseline"
PERTURBED_STATE_ID = "state:flagship-perturbed"
STATE_FIELDS_REPRESENTATION_ID = "representation:flagship-state-fields"
TRAJECTORY_REPRESENTATION_ID = "representation:flagship-well-trajectory"
TRAJECTORY_SUPPORT_ID = "support:flagship-well-trajectory"
OBSERVATION_SUPPORT_ID = "support:flagship-pressure-observation"
OBSERVATION_ID = "observation:flagship-well-pressure"
OBSERVATION_REPRESENTATION_ID = "representation:flagship-well-pressure-evidence"
FRAME_ID = "frame:structural-depth-x"
REGION_SELECTION_BINDING_ID = "binding:reservoir_selection:flagship-baseline"


@dataclass(frozen=True)
class FlagshipWorldResult:
    flagship_input: CompiledFlagshipInput
    structural_result: StructuralWorldResult
    enriched_world: World
    baseline_world: World
    world: World
    baseline_bundle: XarrayBundle
    perturbed_bundle: XarrayBundle
    trajectory_bytes: bytes
    observation_rows: tuple[PressureObservationRow, ...]
    observation_bytes: bytes
    observation: Observation
    observation_seed_lineage: dict[str, object]

    @property
    def normalized_input_bytes(self) -> bytes:
        return canonical_flagship_input_bytes(self.flagship_input)

    @property
    def structural_dataset(self) -> xr.Dataset:
        return self.structural_result.dataset

    @property
    def baseline_dataset(self) -> xr.Dataset:
        return self.baseline_bundle.to_dataset()

    @property
    def perturbed_dataset(self) -> xr.Dataset:
        return self.perturbed_bundle.to_dataset()


def _ref(kind: SubjectKind, subject_id: str, version: str | None = None) -> SubjectRef:
    return SubjectRef(
        kind=kind,
        subject_id=subject_id,
        representation_version=version,
    )


def _state_ref(state_id: str) -> SubjectRef:
    return _ref(SubjectKind.WORLD_STATE, state_id)


def _binding_ref(binding_id: str) -> SubjectRef:
    return _ref(SubjectKind.FIELD_BINDING, binding_id)


def _representation_ref(representation_id: str, version: str) -> SubjectRef:
    return _ref(SubjectKind.REPRESENTATION, representation_id, version)


def _region_entity_id(value: CompiledFlagshipInput) -> str:
    return f"reservoir-region:{value.reservoir_region.id}"


def _well_entity_id(value: CompiledFlagshipInput) -> str:
    return f"well:{value.well.id}"


def _field_definition(
    name: str,
    unit: str,
    *,
    missingness: Missingness,
) -> FieldDefinition:
    return FieldDefinition(
        field_id=f"field:{name}",
        canonical_name=name,
        unit=unit,
        value_kind=ValueKind.CONTINUOUS,
        physical_rank=PhysicalRank.SCALAR,
        missingness=missingness,
        admissible_support_kinds=(SupportKind.REGULAR_GRID,),
        domain_constraint_refs=(f"geoscience:flagship:{name}",),
        provenance_ids=("provenance:flagship-semantics",),
    )


def _verify_authority(world: World, flagship_input: CompiledFlagshipInput) -> SubjectRef:
    flagship_ref = _representation_ref(
        FLAGSHIP_INPUT_REPRESENTATION_ID,
        FLAGSHIP_INPUT_REPRESENTATION_VERSION,
    )
    registered = next((item for item in world.representations if item.ref == flagship_ref), None)
    if registered is None:
        raise ValueError("World does not contain the flagship input Representation")
    if registered.content_sha256 != flagship_input_sha256(flagship_input):
        raise ValueError("compiled flagship input does not match the World-bound input")
    if registered.artifact_uri != FLAGSHIP_INPUT_ARTIFACT_URI:
        raise ValueError("flagship input Representation has an unexpected artifact URI")
    structural_ref = _representation_ref(
        STRUCTURAL_INPUT_REPRESENTATION_ID,
        STRUCTURAL_INPUT_REPRESENTATION_VERSION,
    )
    structural = next((item for item in world.representations if item.ref == structural_ref), None)
    if structural is None or structural.content_sha256 != structural_input_sha256(
        flagship_input.structural
    ):
        raise ValueError("flagship structural input does not match the structural World")
    return flagship_ref


def bootstrap_flagship_semantics(
    structural_result: StructuralWorldResult,
    flagship_input: CompiledFlagshipInput,
) -> tuple[World, bytes]:
    """Add authored semantic objects and exact input without changing structural state."""
    if structural_result.structural_input != flagship_input.structural:
        raise ValueError("flagship input does not match the completed structural result")
    world = structural_result.world
    region_id = _region_entity_id(flagship_input)
    well_id = _well_entity_id(flagship_input)
    formation_id = f"formation:{flagship_input.reservoir_region.formation_id}"
    fault_id = f"fault:{flagship_input.reservoir_region.intersecting_fault_id}"
    existing_entities = {item.entity_id for item in world.entities}
    if formation_id not in existing_entities or fault_id not in existing_entities:
        raise ValueError("flagship semantic references are absent from the structural World")

    input_ref = _representation_ref(
        FLAGSHIP_INPUT_REPRESENTATION_ID,
        FLAGSHIP_INPUT_REPRESENTATION_VERSION,
    )
    structural_input_ref = _representation_ref(
        STRUCTURAL_INPUT_REPRESENTATION_ID,
        STRUCTURAL_INPUT_REPRESENTATION_VERSION,
    )
    trajectory_ref = _representation_ref(TRAJECTORY_REPRESENTATION_ID, "v1")
    trajectory_bytes = well_trajectory_csv_bytes(flagship_input)
    flagship_representation = Representation(
        representation_id=FLAGSHIP_INPUT_REPRESENTATION_ID,
        version=FLAGSHIP_INPUT_REPRESENTATION_VERSION,
        subjects=(_state_ref(STRUCTURAL_STATE_ID),),
        kind=RepresentationKind.TABLE,
        artifact_uri=FLAGSHIP_INPUT_ARTIFACT_URI,
        content_sha256=flagship_input_sha256(flagship_input),
        media_type="application/json",
        derived_from=(structural_input_ref,),
        provenance_ids=("provenance:flagship-input",),
    )
    trajectory_support = Support(
        support_id=TRAJECTORY_SUPPORT_ID,
        support_kind=SupportKind.CURVE,
        dimension_names=("depth",),
        shape=(2,),
        reference_frame_id=FRAME_ID,
        provenance_ids=("provenance:flagship-well-trajectory",),
    )
    observation_support = Support(
        support_id=OBSERVATION_SUPPORT_ID,
        support_kind=SupportKind.POINTS,
        dimension_names=("depth",),
        shape=(len(flagship_input.observation.sample_depths_m),),
        reference_frame_id=FRAME_ID,
        provenance_ids=("provenance:flagship-semantics",),
    )
    trajectory_representation = Representation(
        representation_id=TRAJECTORY_REPRESENTATION_ID,
        version="v1",
        subjects=(_ref(SubjectKind.ENTITY, well_id),),
        kind=RepresentationKind.CURVE,
        artifact_uri="artifact://wells/flagship-well-trajectory.csv",
        content_sha256=hashlib.sha256(trajectory_bytes).hexdigest(),
        media_type="text/csv",
        support_id=TRAJECTORY_SUPPORT_ID,
        reference_frame_id=FRAME_ID,
        dimensions=("depth",),
        derived_from=(input_ref,),
        provenance_ids=("provenance:flagship-well-trajectory",),
    )
    entities = (
        Entity(
            entity_id=region_id,
            entity_type="geoscience:reservoir_region",
            label=flagship_input.reservoir_region.label,
            provenance_ids=("provenance:flagship-semantics",),
        ),
        Entity(
            entity_id=well_id,
            entity_type="geoscience:well",
            label=flagship_input.well.label,
            provenance_ids=("provenance:flagship-semantics",),
        ),
    )
    relations = (
        Relation(
            relation_id="relation:flagship-region-part-of-formation",
            source_entity_id=region_id,
            relation_type="geoscience:part_of",
            target_entity_id=formation_id,
            provenance_ids=("provenance:flagship-semantics",),
        ),
        Relation(
            relation_id="relation:flagship-well-penetrates-region",
            source_entity_id=well_id,
            relation_type="geoscience:penetrates",
            target_entity_id=region_id,
            provenance_ids=("provenance:flagship-semantics",),
        ),
        Relation(
            relation_id="relation:flagship-well-penetrates-formation",
            source_entity_id=well_id,
            relation_type="geoscience:penetrates",
            target_entity_id=formation_id,
            provenance_ids=("provenance:flagship-semantics",),
        ),
        Relation(
            relation_id="relation:flagship-fault-intersects-region",
            source_entity_id=fault_id,
            relation_type="geoscience:intersects",
            target_entity_id=region_id,
            provenance_ids=("provenance:flagship-semantics",),
        ),
        Relation(
            relation_id="relation:flagship-fault-intersects-formation",
            source_entity_id=fault_id,
            relation_type="geoscience:intersects",
            target_entity_id=formation_id,
            provenance_ids=("provenance:flagship-semantics",),
        ),
    )
    definitions = (
        _field_definition("pressure", "Pa", missingness=Missingness.ALLOW),
        _field_definition(
            "pressure_perturbation", "Pa", missingness=Missingness.FORBID
        ),
        _field_definition("temperature", "degC", missingness=Missingness.FORBID),
    )
    semantic_outputs = (
        *(_ref(SubjectKind.ENTITY, item.entity_id) for item in entities),
        *(_ref(SubjectKind.RELATION, item.relation_id) for item in relations),
        *(_ref(SubjectKind.FIELD_DEFINITION, item.field_id) for item in definitions),
        _ref(SubjectKind.SUPPORT, OBSERVATION_SUPPORT_ID),
    )
    provenance = (
        Provenance(
            provenance_id="provenance:flagship-input",
            activity_type="geoscience:flagship_input_compilation",
            method="canonical_flagship_input_json_v1",
            inputs=(_state_ref(STRUCTURAL_STATE_ID), structural_input_ref),
            outputs=(input_ref,),
            parent_provenance_ids=("provenance:structural-transition",),
            parameters=(("content_sha256", flagship_representation.content_sha256),),
        ),
        Provenance(
            provenance_id="provenance:flagship-semantics",
            activity_type="geoscience:flagship_semantic_bootstrap",
            method="explicit authored ReservoirRegion, Well, and relations",
            inputs=(
                _state_ref(STRUCTURAL_STATE_ID),
                input_ref,
                _ref(SubjectKind.ENTITY, formation_id),
                _ref(SubjectKind.ENTITY, fault_id),
            ),
            outputs=semantic_outputs,
            parent_provenance_ids=("provenance:flagship-input",),
        ),
        Provenance(
            provenance_id="provenance:flagship-well-trajectory",
            activity_type="geoscience:well_trajectory_compilation",
            method="explicit vertical 2-D trajectory endpoints",
            inputs=(input_ref, _ref(SubjectKind.ENTITY, well_id)),
            outputs=(_ref(SubjectKind.SUPPORT, TRAJECTORY_SUPPORT_ID), trajectory_ref),
            parent_provenance_ids=("provenance:flagship-semantics",),
        ),
    )
    payload = world.model_dump(mode="python")
    payload["entities"] = world.entities + entities
    payload["relations"] = world.relations + relations
    payload["field_definitions"] = world.field_definitions + definitions
    payload["supports"] = world.supports + (trajectory_support, observation_support)
    payload["representations"] = world.representations + (
        flagship_representation,
        trajectory_representation,
    )
    payload["provenance"] = world.provenance + provenance
    return World.model_validate(payload), trajectory_bytes


def _state_binding(
    name: str,
    state_id: str,
    version: str,
    subject: SubjectRef,
    provenance_id: str,
    valid_from: TemporalValue,
) -> FieldBinding:
    return FieldBinding(
        binding_id=f"binding:{name}:{state_id.split(':')[-1]}",
        field_definition_id=f"field:{name}",
        subject=subject,
        world_state_id=state_id,
        representation=_representation_ref(STATE_FIELDS_REPRESENTATION_ID, version),
        support_id=SUPPORT_ID,
        scale_label="structural-grid-cell",
        valid_from=valid_from,
        provenance_ids=(provenance_id,),
    )


def _portable_bundle(bundle: XarrayBundle, version: str) -> XarrayBundle:
    representation = bundle.representation.model_copy(
        update={
            "artifact_uri": (
                f"artifact://representations/flagship-state-fields/{version}/metadata.json"
            )
        }
    )
    return XarrayBundle(bundle.to_dataset(), representation, bundle.variable_bindings)


class BaselineTransition:
    transition_id = "transition:flagship-baseline-v1"

    def __init__(
        self,
        flagship_input: CompiledFlagshipInput,
        structural_bundle: XarrayBundle,
    ) -> None:
        self.flagship_input = flagship_input
        self.structural_bundle = structural_bundle
        self.bundle: XarrayBundle | None = None

    def apply(self, world: World, input_state: WorldState) -> TransitionResult:
        if input_state.state_id != STRUCTURAL_STATE_ID:
            raise ValueError("baseline requires the structural final state")
        input_ref = _verify_authority(world, self.flagship_input)
        if self.structural_bundle.representation not in world.representations:
            raise ValueError("structural bundle is not registered in the World")
        dataset = compute_baseline_fields(
            self.flagship_input,
            self.structural_bundle.to_dataset(),
        )
        provenance_id = "provenance:flagship-baseline"
        representation_ref = _representation_ref(STATE_FIELDS_REPRESENTATION_ID, "v1")
        time = TemporalValue(relative_value=0.0, relative_unit="days")
        state_field_bindings = {
            "reservoir_selection": FieldBinding(
                binding_id=REGION_SELECTION_BINDING_ID,
                field_definition_id="field:reservoir_selection",
                subject=_ref(
                    SubjectKind.ENTITY,
                    _region_entity_id(self.flagship_input),
                ),
                world_state_id=BASELINE_STATE_ID,
                representation=representation_ref,
                support_id=SUPPORT_ID,
                scale_label="structural-grid-cell",
                valid_from=time,
                provenance_ids=(provenance_id,),
            ),
            "pressure": _state_binding(
                "pressure",
                BASELINE_STATE_ID,
                "v1",
                _ref(SubjectKind.ENTITY, _region_entity_id(self.flagship_input)),
                provenance_id,
                time,
            ),
            "temperature": _state_binding(
                "temperature",
                BASELINE_STATE_ID,
                "v1",
                _ref(SubjectKind.ENTITY, ROOT_ENTITY_ID),
                provenance_id,
                time,
            ),
        }
        bindings = tuple(state_field_bindings.values())
        state = WorldState(
            state_id=BASELINE_STATE_ID,
            world_id=world.world_id,
            role=WorldStateRole.SIMULATED,
            valid_from=time,
            parent_state_id=input_state.state_id,
            field_binding_ids=tuple(item.binding_id for item in bindings),
            representation_refs=(representation_ref, input_ref),
            provenance_ids=(provenance_id,),
        )
        provenance = Provenance(
            provenance_id=provenance_id,
            activity_type="geoscience:illustrative_baseline_fields",
            method=(
                "explicit ReservoirRegion selection binding plus hydrostatic pressure "
                "and linear geothermal-gradient benchmarks"
            ),
            inputs=(
                _state_ref(input_state.state_id),
                input_ref,
                self.structural_bundle.representation.ref,
                _binding_ref("binding:reservoir_selection:structural-final"),
                _ref(SubjectKind.ENTITY, _region_entity_id(self.flagship_input)),
            ),
            outputs=(
                _state_ref(state.state_id),
                *(_binding_ref(item.binding_id) for item in bindings),
                representation_ref,
            ),
            parent_provenance_ids=(
                "provenance:flagship-semantics",
                "provenance:stratigraphic-assignment",
            ),
            parameters=(
                ("pressure_method", "illustrative_hydrostatic_pressure_v1"),
                ("temperature_method", "linear_geothermal_gradient_v1"),
                ("region_binding_method", "explicit_reservoir_region_binding_v1"),
            ),
        )
        bundle = create_xarray_bundle(
            dataset,
            world_id=world.world_id,
            state=state,
            support=world.supports[0],
            reference_frame=world.reference_frames[0],
            representation_id=STATE_FIELDS_REPRESENTATION_ID,
            version="v1",
            variable_bindings=state_field_bindings,
            field_definitions=world.field_definitions,
            provenance=provenance,
            derived_from=(self.structural_bundle.representation.ref, input_ref),
        )
        self.bundle = _portable_bundle(bundle, "v1")
        return TransitionResult(
            state=state,
            field_bindings=bindings,
            representations=(self.bundle.representation,),
            provenance=(provenance,),
        )


class PressurePerturbationTransition:
    transition_id = "transition:flagship-pressure-perturbation-v1"

    def __init__(
        self,
        flagship_input: CompiledFlagshipInput,
        baseline_bundle: XarrayBundle,
    ) -> None:
        self.flagship_input = flagship_input
        self.baseline_bundle = baseline_bundle
        self.bundle: XarrayBundle | None = None

    def apply(self, world: World, input_state: WorldState) -> TransitionResult:
        if input_state.state_id != BASELINE_STATE_ID:
            raise ValueError("pressure perturbation requires the flagship baseline state")
        input_ref = _verify_authority(world, self.flagship_input)
        if self.baseline_bundle.representation not in world.representations:
            raise ValueError("baseline bundle is not registered in the World")
        dataset = compute_perturbed_pressure_fields(
            self.flagship_input,
            self.baseline_bundle.to_dataset(),
        )
        provenance_id = "provenance:flagship-pressure-perturbation"
        representation_ref = _representation_ref(STATE_FIELDS_REPRESENTATION_ID, "v2")
        time = TemporalValue(
            relative_value=self.flagship_input.perturbation.model_time_days,
            relative_unit="days",
        )
        region_ref = _ref(SubjectKind.ENTITY, _region_entity_id(self.flagship_input))
        bindings = {
            "pressure": _state_binding(
                "pressure",
                PERTURBED_STATE_ID,
                "v2",
                region_ref,
                provenance_id,
                time,
            ),
            "pressure_perturbation": _state_binding(
                "pressure_perturbation",
                PERTURBED_STATE_ID,
                "v2",
                region_ref,
                provenance_id,
                time,
            ),
            "temperature": _state_binding(
                "temperature",
                PERTURBED_STATE_ID,
                "v2",
                _ref(SubjectKind.ENTITY, ROOT_ENTITY_ID),
                provenance_id,
                time,
            ),
        }
        state = WorldState(
            state_id=PERTURBED_STATE_ID,
            world_id=world.world_id,
            role=WorldStateRole.SIMULATED,
            valid_from=time,
            parent_state_id=input_state.state_id,
            field_binding_ids=tuple(item.binding_id for item in bindings.values()),
            representation_refs=(representation_ref, input_ref),
            provenance_ids=(provenance_id,),
        )
        provenance = Provenance(
            provenance_id=provenance_id,
            activity_type="geoscience:analytic_pressure_perturbation",
            method="explicit reservoir-masked Gaussian-like pressure benchmark",
            inputs=(
                _state_ref(input_state.state_id),
                input_ref,
                self.baseline_bundle.representation.ref,
                _binding_ref("binding:pressure:flagship-baseline"),
                _binding_ref(REGION_SELECTION_BINDING_ID),
                region_ref,
            ),
            outputs=(
                _state_ref(state.state_id),
                *(_binding_ref(item.binding_id) for item in bindings.values()),
                representation_ref,
            ),
            parent_provenance_ids=("provenance:flagship-baseline",),
            parameters=(
                ("method_id", "analytic_pressure_perturbation_v1"),
                ("model_time_days", self.flagship_input.perturbation.model_time_days),
                ("temperature_behavior", "copied unchanged from baseline"),
            ),
        )
        bundle = create_xarray_bundle(
            dataset,
            world_id=world.world_id,
            state=state,
            support=world.supports[0],
            reference_frame=world.reference_frames[0],
            representation_id=STATE_FIELDS_REPRESENTATION_ID,
            version="v2",
            variable_bindings=bindings,
            field_definitions=world.field_definitions,
            provenance=provenance,
            derived_from=(
                self.baseline_bundle.representation.ref,
                input_ref,
            ),
        )
        self.bundle = _portable_bundle(bundle, "v2")
        return TransitionResult(
            state=state,
            field_bindings=tuple(bindings.values()),
            representations=(self.bundle.representation,),
            provenance=(provenance,),
        )


def _append_observation(
    world: World,
    flagship_input: CompiledFlagshipInput,
    perturbed_bundle: XarrayBundle,
) -> tuple[
    World,
    Observation,
    tuple[PressureObservationRow, ...],
    bytes,
    dict[str, object],
]:
    input_ref = _verify_authority(world, flagship_input)
    rows, seed_lineage = sample_well_pressure(
        flagship_input,
        perturbed_bundle.to_dataset(),
    )
    evidence_bytes = observation_csv_bytes(rows)
    evidence_ref = _representation_ref(OBSERVATION_REPRESENTATION_ID, "v1")
    observation_ref = _ref(SubjectKind.OBSERVATION, OBSERVATION_ID)
    trajectory_ref = _representation_ref(TRAJECTORY_REPRESENTATION_ID, "v1")
    time = TemporalValue(
        relative_value=flagship_input.perturbation.model_time_days,
        relative_unit="days",
    )
    observation = Observation(
        observation_id=OBSERVATION_ID,
        world_id=world.world_id,
        status=ObservationStatus.SYNTHETIC,
        subjects=(
            _ref(SubjectKind.ENTITY, _well_entity_id(flagship_input)),
            _binding_ref("binding:pressure:flagship-perturbed"),
            _state_ref(PERTURBED_STATE_ID),
        ),
        representation=evidence_ref,
        valid_time=time,
        quality=(
            ("sampling_method", flagship_input.observation.sampling_method),
            ("noise_sigma_pa", flagship_input.observation.noise_sigma_pa),
        ),
        provenance_ids=("provenance:flagship-pressure-observation",),
    )
    evidence = Representation(
        representation_id=OBSERVATION_REPRESENTATION_ID,
        version="v1",
        subjects=(
            observation_ref,
            _ref(SubjectKind.ENTITY, _well_entity_id(flagship_input)),
        ),
        kind=RepresentationKind.TABLE,
        artifact_uri="artifact://observations/well-pressure.csv",
        content_sha256=hashlib.sha256(evidence_bytes).hexdigest(),
        media_type="text/csv",
        support_id=OBSERVATION_SUPPORT_ID,
        reference_frame_id=FRAME_ID,
        dimensions=("depth",),
        derived_from=(perturbed_bundle.representation.ref, trajectory_ref),
        provenance_ids=("provenance:flagship-pressure-observation",),
    )
    provenance = Provenance(
        provenance_id="provenance:flagship-pressure-observation",
        activity_type="geoscience:synthetic_pressure_observation",
        method="nearest-cell sampling plus explicit deterministic Gaussian noise",
        inputs=(
            input_ref,
            _state_ref(PERTURBED_STATE_ID),
            perturbed_bundle.representation.ref,
            trajectory_ref,
            _binding_ref("binding:pressure:flagship-perturbed"),
            _ref(SubjectKind.ENTITY, _well_entity_id(flagship_input)),
        ),
        outputs=(observation_ref, evidence_ref),
        parent_provenance_ids=("provenance:flagship-pressure-perturbation",),
        parameters=(
            ("sampling_method", flagship_input.observation.sampling_method),
            ("noise_sigma_pa", flagship_input.observation.noise_sigma_pa),
            ("noise_seed", flagship_input.observation.noise_seed),
            ("noise_namespace", flagship_input.observation.noise_namespace),
        ),
    )
    updated = world.with_records(
        representations=(evidence,),
        observations=(observation,),
        provenance=(provenance,),
    )
    return updated, observation, rows, evidence_bytes, seed_lineage


def run_flagship_world(spec: FlagshipSpec) -> FlagshipWorldResult:
    """Run the complete flagship story through the real World contracts."""
    flagship_input = compile_flagship_input(spec)
    structural_result = run_compiled_structural_world(flagship_input.structural)
    enriched_world, trajectory_bytes = bootstrap_flagship_semantics(
        structural_result,
        flagship_input,
    )
    baseline_transition = BaselineTransition(
        flagship_input,
        structural_result.stratigraphy_bundle,
    )
    baseline_execution = apply_transition(
        enriched_world,
        STRUCTURAL_STATE_ID,
        baseline_transition,
    )
    if baseline_transition.bundle is None:
        raise RuntimeError("baseline transition did not produce an immutable bundle")
    perturbation_transition = PressurePerturbationTransition(
        flagship_input,
        baseline_transition.bundle,
    )
    perturbation_execution = apply_transition(
        baseline_execution.world,
        BASELINE_STATE_ID,
        perturbation_transition,
    )
    if perturbation_transition.bundle is None:
        raise RuntimeError("perturbation transition did not produce an immutable bundle")
    (
        final_world,
        observation,
        observation_rows,
        evidence_bytes,
        seed_lineage,
    ) = _append_observation(
        perturbation_execution.world,
        flagship_input,
        perturbation_transition.bundle,
    )
    return FlagshipWorldResult(
        flagship_input=flagship_input,
        structural_result=structural_result,
        enriched_world=enriched_world,
        baseline_world=baseline_execution.world,
        world=final_world,
        baseline_bundle=baseline_transition.bundle,
        perturbed_bundle=perturbation_transition.bundle,
        trajectory_bytes=trajectory_bytes,
        observation_rows=observation_rows,
        observation_bytes=evidence_bytes,
        observation=observation,
        observation_seed_lineage=seed_lineage,
    )
