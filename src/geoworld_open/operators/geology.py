"""Analytic layered geology with optional explicit fold and planar fault."""

from __future__ import annotations

from typing import Any

import numpy as np

from geoworld_open.schema import ScenarioSpec

from .base import OperatorMetadata


class LayeredGeologyOperator:
    metadata = OperatorMetadata(
        name="layered_geology",
        version="1.0",
        description="Analytic layers with optional sinusoidal fold and planar fault displacement.",
    )

    def run(self, arrays: dict[str, np.ndarray], context: dict[str, Any]) -> dict[str, np.ndarray]:
        del arrays
        scenario: ScenarioSpec = context["scenario"]
        grid = scenario.grid
        x = np.arange(grid.nx, dtype=float) * grid.dx_m
        z = np.arange(grid.nz, dtype=float) * grid.dz_m
        xx, zz = np.meshgrid(x, z)
        source_depth = zz.copy()

        if scenario.fold:
            phase = np.deg2rad(scenario.fold.phase_deg)
            displacement = scenario.fold.amplitude_m * np.sin(
                2.0 * np.pi * xx / scenario.fold.wavelength_m + phase
            )
            source_depth -= displacement

        fault_mask = np.zeros_like(source_depth, dtype=bool)
        if scenario.fault:
            fault = scenario.fault
            tangent = np.tan(np.deg2rad(fault.dip_degrees))
            trace_x = fault.x_position_m + (zz - fault.reference_depth_m) / tangent
            fault_mask = xx >= trace_x if fault.downthrown_side == "right" else xx <= trace_x
            source_depth[fault_mask] -= fault.throw_m

        total_depth = grid.nz * grid.dz_m
        source_depth = np.clip(source_depth, 0.0, np.nextafter(total_depth, 0.0))
        boundaries = np.cumsum([layer.thickness_m for layer in scenario.layers])
        layer_index = np.searchsorted(boundaries, source_depth, side="right")
        layer_index = np.clip(layer_index, 0, len(scenario.layers) - 1).astype(np.int16)

        return {
            "x_m": x,
            "z_m": z,
            "layer_index": layer_index,
            "fault_side_mask": fault_mask.astype(np.uint8),
        }

