"""Simplified linearized Aki-Richards reflectivity and angle stacks."""

from __future__ import annotations

from typing import Any

import numpy as np

from geoworld_open.schema import ScenarioSpec

from .base import OperatorMetadata
from .seismic import convolve_traces


def aki_richards_gather(
    vp: np.ndarray,
    vs: np.ndarray,
    density: np.ndarray,
    angles_deg: np.ndarray,
) -> np.ndarray:
    """Compute a documented three-term linearized Aki-Richards approximation."""
    shape = (angles_deg.size,) + vp.shape
    gather = np.zeros(shape, dtype=float)
    vp1, vp2 = vp[:-1], vp[1:]
    vs1, vs2 = vs[:-1], vs[1:]
    rho1, rho2 = density[:-1], density[1:]
    vp_avg = np.maximum((vp1 + vp2) * 0.5, 1e-12)
    vs_avg = np.maximum((vs1 + vs2) * 0.5, 1e-12)
    rho_avg = np.maximum((rho1 + rho2) * 0.5, 1e-12)
    dvp = (vp2 - vp1) / vp_avg
    dvs = (vs2 - vs1) / vs_avg
    drho = (rho2 - rho1) / rho_avg
    ratio_sq = (vs_avg / vp_avg) ** 2
    intercept = 0.5 * (dvp + drho)
    gradient = 0.5 * dvp - 2.0 * ratio_sq * (drho + 2.0 * dvs)

    for index, angle_deg in enumerate(angles_deg):
        angle = np.deg2rad(angle_deg)
        sin_sq = np.sin(angle) ** 2
        curvature = 0.5 * dvp * (np.tan(angle) ** 2 - sin_sq)
        gather[index, 1:] = intercept + gradient * sin_sq + curvature
    return np.nan_to_num(gather)


class AVOSyntheticOperator:
    metadata = OperatorMetadata(
        name="linearized_aki_richards",
        version="1.0",
        description="Illustrative Aki-Richards angle reflectivity and configured angle-band stacks.",
    )

    def run(self, arrays: dict[str, np.ndarray], context: dict[str, Any]) -> dict[str, np.ndarray]:
        scenario: ScenarioSpec = context["scenario"]
        angles = np.asarray(scenario.geophysics.angles_deg, dtype=float)
        reflectivity = aki_richards_gather(
            arrays["vp_m_s"], arrays["vs_m_s"], arrays["density_kg_m3"], angles
        )
        wavelet = arrays["ricker_wavelet"]
        convolved = np.stack([convolve_traces(item, wavelet) for item in reflectivity])
        outputs: dict[str, np.ndarray] = {
            "avo_angles_deg": angles,
            "avo_reflectivity_gather": reflectivity,
            "avo_synthetic_gather": convolved,
        }
        for band in scenario.geophysics.angle_bands:
            selected = (angles >= band.min_deg) & (angles <= band.max_deg)
            key = "avo_stack_" + "".join(c if c.isalnum() else "_" for c in band.name.lower()).strip("_")
            outputs[key] = np.mean(convolved[selected], axis=0)
        return outputs

