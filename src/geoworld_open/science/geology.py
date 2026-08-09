"""Explicit analytic structural geology for GeoWorld Open GeoSpec V2."""

from __future__ import annotations

from typing import Any

import numpy as np
import xarray as xr

from geoworld_open.data import create_earth_dataset
from geoworld_open.engine.contracts import (
    OperatorExecutionContext,
    OperatorMetadataV2,
    OperatorResult,
    VariableContract,
)
from geoworld_open.engine.execution import ScientificWorkflowResult, execute_graph
from geoworld_open.schema import ScenarioSpec
from geoworld_open.specs.compatibility import migrate_v1_to_v2
from geoworld_open.specs.models import FaultStructureSpec, FoldStructureSpec, GeoSpecV2


DEPTH_X = ("depth", "x")


def _attrs(
    units: str,
    long_name: str,
    physical_meaning: str,
    operator_id: str,
    method_id: str,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "units": units,
        "long_name": long_name,
        "physical_meaning": physical_meaning,
        "source_operator": operator_id,
        "method_id": method_id,
        **extra,
    }


class StructuralGeometryOperator:
    metadata = OperatorMetadataV2(
        id="structural_geometry",
        version="2.0.0",
        method_id="analytic_source_depth_v1",
        produces=(
            VariableContract("source_depth_m", DEPTH_X, "m", "f"),
            VariableContract("structural_displacement_m", DEPTH_X, "m", "f"),
            VariableContract("fold_displacement_m", DEPTH_X, "m", "f"),
            VariableContract("fault_displacement_m", DEPTH_X, "m", "f"),
            VariableContract("fault_mask", ("fault", "depth", "x"), "1", "b"),
            VariableContract("boundary_clipped_mask", DEPTH_X, "1", "b"),
        ),
        assumptions=(
            "Coordinates are Cartesian cell centers with x increasing right and depth positive down.",
            "Fault dip is measured from horizontal toward increasing depth.",
            "Listed structures are applied sequentially using source-depth coordinate mapping.",
            "Normal displacement moves the selected block down; reverse displacement moves it up.",
            "Source depths outside the model are clipped to the nearest valid model depth.",
        ),
        references=("General analytic coordinate transformations for synthetic structural models.",),
    )

    def execute(
        self,
        dataset: xr.Dataset,
        context: OperatorExecutionContext,
    ) -> OperatorResult:
        x = np.asarray(dataset.coords["x"].values)
        depth = np.asarray(dataset.coords["depth"].values)
        xx, dd = np.meshgrid(x, depth)
        source_depth = dd.copy()
        fold_displacement = np.zeros_like(source_depth)
        fault_displacement = np.zeros_like(source_depth)
        fault_ids: list[str] = []
        fault_masks: list[np.ndarray] = []

        for structure in context.spec.structures:
            if isinstance(structure, FoldStructureSpec):
                phase_rad = np.deg2rad(structure.phase_deg)
                displacement = structure.amplitude_m * np.sin(
                    2.0 * np.pi * (xx - structure.x_origin_m) / structure.wavelength_m
                    + phase_rad
                )
                source_depth -= displacement
                fold_displacement += displacement
                continue

            assert isinstance(structure, FaultStructureSpec)
            direction = 1.0 if structure.dip_direction == "positive_x" else -1.0
            trace_x = structure.x_position_m + direction * (
                source_depth - structure.reference_depth_m
            ) / np.tan(np.deg2rad(structure.dip_deg))
            mask = xx >= trace_x if structure.displaced_side == "positive_x" else xx <= trace_x
            signed_throw = structure.throw_m if structure.displacement == "normal" else -structure.throw_m
            source_depth[mask] -= signed_throw
            fault_displacement[mask] += signed_throw
            fault_ids.append(structure.id)
            fault_masks.append(mask)

        grid = context.spec.grid
        depth_min = grid.depth_origin_m
        depth_max = depth_min + grid.thickness_m
        clipped = (source_depth < depth_min) | (source_depth >= depth_max)
        source_depth = np.clip(source_depth, depth_min, np.nextafter(depth_max, depth_min))
        combined_displacement = dd - source_depth
        stacked_faults = (
            np.stack(fault_masks).astype(bool)
            if fault_masks
            else np.empty((0, grid.ndepth, grid.nx), dtype=bool)
        )
        operator_id = self.metadata.id
        method_id = self.metadata.method_id
        fragment = xr.Dataset(
            data_vars={
                "source_depth_m": (
                    DEPTH_X,
                    source_depth,
                    _attrs("m", "source depth", "undeformed depth sampled by each cell", operator_id, method_id),
                ),
                "structural_displacement_m": (
                    DEPTH_X,
                    combined_displacement,
                    _attrs("m", "total structural displacement", "positive values shift material deeper", operator_id, method_id),
                ),
                "fold_displacement_m": (
                    DEPTH_X,
                    fold_displacement,
                    _attrs("m", "fold displacement", "cumulative listed fold displacement", operator_id, method_id),
                ),
                "fault_displacement_m": (
                    DEPTH_X,
                    fault_displacement,
                    _attrs("m", "fault displacement", "cumulative signed fault throw", operator_id, method_id),
                ),
                "fault_mask": (
                    ("fault", "depth", "x"),
                    stacked_faults,
                    _attrs("1", "fault displaced-side mask", "cells selected by each explicit fault", operator_id, method_id),
                ),
                "boundary_clipped_mask": (
                    DEPTH_X,
                    clipped.astype(bool),
                    _attrs("1", "source-depth clipping mask", "cells whose mapped source depth crossed the model boundary", operator_id, method_id),
                ),
            },
            coords={"depth": dataset.coords["depth"], "x": dataset.coords["x"], "fault": fault_ids},
        )
        fragment.coords["fault"].attrs = {"units": "1", "long_name": "explicit fault identifier"}
        return OperatorResult(
            dataset=fragment,
            diagnostics={
                "structure_count": len(context.spec.structures),
                "fault_count": len(fault_ids),
                "clipped_cell_count": int(np.count_nonzero(clipped)),
                "operation_order": [structure.id for structure in context.spec.structures],
            },
        )


class FaciesAssignmentOperator:
    metadata = OperatorMetadataV2(
        id="facies_assignment",
        version="2.0.0",
        method_id="explicit_layer_lookup_v1",
        dependencies=("structural_geometry",),
        requires=(VariableContract("source_depth_m", DEPTH_X, "m", "f"),),
        produces=(
            VariableContract("layer_index", DEPTH_X, "1", "i"),
            VariableContract("facies", DEPTH_X, "1", "i"),
            VariableContract("porosity", DEPTH_X, "1", "f"),
            VariableContract("reservoir_mask", DEPTH_X, "1", "b"),
        ),
        assumptions=(
            "Layer properties are explicit GeoSpec inputs and are piecewise constant.",
            "Facies assignment follows mapped source depth after all listed structures.",
        ),
        references=("General interval lookup on explicit stratigraphic boundaries.",),
    )

    def execute(
        self,
        dataset: xr.Dataset,
        context: OperatorExecutionContext,
    ) -> OperatorResult:
        spec = context.spec
        boundaries = spec.grid.depth_origin_m + np.cumsum(
            [layer.thickness_m for layer in spec.layers]
        )
        source_depth = np.asarray(dataset["source_depth_m"].values)
        layer_index = np.searchsorted(boundaries, source_depth, side="right")
        layer_index = np.clip(layer_index, 0, len(spec.layers) - 1).astype(np.int16)
        facies_by_id = {facies.id: facies for facies in spec.facies}
        facies_codes = np.asarray(
            [facies_by_id[layer.facies_id].code for layer in spec.layers], dtype=np.int16
        )
        porosities = np.asarray([layer.porosity_fraction for layer in spec.layers], dtype=float)
        reservoir_flags = np.asarray([layer.is_reservoir for layer in spec.layers], dtype=bool)
        facies = facies_codes[layer_index]
        porosity = porosities[layer_index]
        reservoir_mask = reservoir_flags[layer_index]
        facies_map = {facies.code: facies.id for facies in spec.facies}
        flag_values = sorted(facies_map)
        operator_id = self.metadata.id
        method_id = self.metadata.method_id
        coords = {"depth": dataset.coords["depth"], "x": dataset.coords["x"]}
        fragment = xr.Dataset(
            data_vars={
                "layer_index": (
                    DEPTH_X,
                    layer_index,
                    _attrs(
                        "1",
                        "zero-based layer index",
                        "index into the explicit GeoSpec layer sequence",
                        operator_id,
                        method_id,
                        layer_ids=[layer.id for layer in spec.layers],
                    ),
                ),
                "facies": (
                    DEPTH_X,
                    facies,
                    _attrs(
                        "1",
                        "categorical facies code",
                        "explicit facies assigned from the GeoSpec layer",
                        operator_id,
                        method_id,
                        flag_values=flag_values,
                        flag_meanings=" ".join(facies_map[value] for value in flag_values),
                    ),
                ),
                "porosity": (
                    DEPTH_X,
                    porosity,
                    _attrs("1", "porosity fraction", "explicit bulk-volume pore fraction", operator_id, method_id),
                ),
                "reservoir_mask": (
                    DEPTH_X,
                    reservoir_mask.astype(bool),
                    _attrs("1", "reservoir mask", "cells belonging to explicitly marked reservoir layers", operator_id, method_id),
                ),
            },
            coords=coords,
        )
        return OperatorResult(
            dataset=fragment,
            diagnostics={
                "layer_count": len(spec.layers),
                "facies_codes": flag_values,
                "reservoir_cell_count": int(np.count_nonzero(reservoir_mask)),
            },
        )


def default_structural_operators() -> tuple[StructuralGeometryOperator, FaciesAssignmentOperator]:
    return StructuralGeometryOperator(), FaciesAssignmentOperator()


def run_structural_workflow(spec: GeoSpecV2 | ScenarioSpec) -> ScientificWorkflowResult:
    """Run the native V2 structural graph or an explicit structural-only V1 migration."""
    compatibility: dict[str, Any] | None = None
    if isinstance(spec, ScenarioSpec):
        migration = migrate_v1_to_v2(spec)
        spec = migration.spec
        compatibility = {
            "source_schema_version": migration.source_schema_version,
            "mode": migration.compatibility_mode,
            "notes": list(migration.notes),
        }
    dataset = create_earth_dataset(spec)
    return execute_graph(
        spec,
        default_structural_operators(),
        dataset,
        compatibility=compatibility,
    )
