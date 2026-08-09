"""Map explicit YAML properties to the analytic geology."""

from __future__ import annotations

from typing import Any

import numpy as np

from geoworld_open.schema import ScenarioSpec

from .base import OperatorMetadata


class ExplicitPropertyOperator:
    metadata = OperatorMetadata(
        name="explicit_properties",
        version="1.0",
        description="Assigns user-specified layer properties and an optional clipped CO2 ellipse.",
    )

    def run(self, arrays: dict[str, np.ndarray], context: dict[str, Any]) -> dict[str, np.ndarray]:
        scenario: ScenarioSpec = context["scenario"]
        layer_index = arrays["layer_index"]
        shape = layer_index.shape
        porosity = np.zeros(shape, dtype=float)
        saturation = np.zeros(shape, dtype=float)
        vp = np.zeros(shape, dtype=float)
        vs = np.zeros(shape, dtype=float)
        density = np.zeros(shape, dtype=float)

        for index, layer in enumerate(scenario.layers):
            mask = layer_index == index
            porosity[mask] = layer.porosity
            saturation[mask] = layer.saturation
            vp[mask] = layer.vp_m_s
            vs[mask] = layer.vs_m_s
            density[mask] = layer.density_kg_m3

        plume_mask = np.zeros(shape, dtype=bool)
        if scenario.co2_change:
            change = scenario.co2_change
            xx, zz = np.meshgrid(arrays["x_m"], arrays["z_m"])
            ellipse = (
                ((xx - change.center_x_m) / change.radius_x_m) ** 2
                + ((zz - change.center_z_m) / change.radius_z_m) ** 2
                <= 1.0
            )
            target_index = next(
                index for index, layer in enumerate(scenario.layers) if layer.name == change.target_layer
            )
            plume_mask = ellipse & (layer_index == target_index)
            saturation[plume_mask] = change.saturation
            vp[plume_mask] *= change.vp_multiplier
            vs[plume_mask] *= change.vs_multiplier
            density[plume_mask] *= change.density_multiplier

        return {
            "porosity": porosity,
            "saturation": saturation,
            "vp_m_s": vp,
            "vs_m_s": vs,
            "density_kg_m3": density,
            "co2_change_mask": plume_mask.astype(np.uint8),
        }

