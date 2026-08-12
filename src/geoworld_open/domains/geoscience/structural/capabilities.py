"""Transparent capability wrappers around pure structural numerical routines."""

from __future__ import annotations

import xarray as xr

from geoworld_open.domains.geoscience.structural.numerics import (
    DEPTH_X,
    assign_stratigraphic_fields,
    compute_structural_geometry,
)
from geoworld_open.domains.geoscience.structural.input import CompiledStructuralInput
from geoworld_open.engine import (
    CapabilityMetadata,
    CapabilityResult,
    ExecutionContext,
    VariableContract,
)


class StructuralGeometryCapability:
    metadata = CapabilityMetadata(
        capability_id="structural_geometry",
        version="3.0.0",
        method_id="analytic_source_depth_v1",
        produces=(
            VariableContract("source_depth_m", DEPTH_X, "m", "f"),
            VariableContract("structural_displacement_m", DEPTH_X, "m", "f"),
            VariableContract("fold_displacement_m", DEPTH_X, "m", "f"),
            VariableContract("fault_displacement_m", DEPTH_X, "m", "f"),
            VariableContract("fault_selection", ("fault", "depth", "x"), "1", "b"),
            VariableContract("boundary_clipped_mask", DEPTH_X, "1", "b"),
        ),
        assumptions=(
            "Coordinates are cell centered with x increasing and depth positive down.",
            "Listed structures are sequential source-depth coordinate transforms.",
            "Normal selected-side displacement is positive; reverse is negative.",
            "Out-of-domain source depth is clipped and diagnosed.",
        ),
        references=("Analytic coordinate transformations for synthetic structures.",),
    )

    def execute(self, dataset: xr.Dataset, context: ExecutionContext) -> CapabilityResult:
        if not isinstance(context.input_data, CompiledStructuralInput):
            raise TypeError("StructuralGeometryCapability requires compiled structural input")
        fragment, diagnostics = compute_structural_geometry(
            context.input_data,
            dataset,
        )
        return CapabilityResult(fragment, diagnostics)


class StratigraphicAssignmentCapability:
    metadata = CapabilityMetadata(
        capability_id="stratigraphic_assignment",
        version="3.0.0",
        method_id="explicit_layer_lookup_v1",
        dependencies=("structural_geometry",),
        requires=(VariableContract("source_depth_m", DEPTH_X, "m", "f"),),
        produces=(
            VariableContract("layer_index", DEPTH_X, "1", "i"),
            VariableContract("facies", DEPTH_X, "1", "i"),
            VariableContract("porosity", DEPTH_X, "1", "f"),
            VariableContract("reservoir_selection", DEPTH_X, "1", "b"),
        ),
        assumptions=(
            "Formation properties are explicit compiled-input values and piecewise constant.",
            "Assignment follows mapped source depth after every listed structure.",
        ),
        references=("Interval lookup on explicit stratigraphic boundaries.",),
    )

    def execute(self, dataset: xr.Dataset, context: ExecutionContext) -> CapabilityResult:
        if not isinstance(context.input_data, CompiledStructuralInput):
            raise TypeError("StratigraphicAssignmentCapability requires compiled structural input")
        fragment, diagnostics = assign_stratigraphic_fields(
            context.input_data,
            dataset,
        )
        return CapabilityResult(fragment, diagnostics)


def structural_capabilities() -> tuple[
    StructuralGeometryCapability,
    StratigraphicAssignmentCapability,
]:
    return StructuralGeometryCapability(), StratigraphicAssignmentCapability()
