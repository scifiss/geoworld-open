"""Explicit V1-to-V2 structural compatibility mapping."""

from __future__ import annotations

import re
from dataclasses import dataclass

from geoworld_open.schema import ScenarioSpec

from .models import GeoSpecV2


def _slug_id(value: str, prefix: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or prefix
    if not slug[0].isalpha():
        slug = f"{prefix}_{slug}"
    return slug


@dataclass(frozen=True)
class V1Migration:
    spec: GeoSpecV2
    source_schema_version: str = "1.0"
    compatibility_mode: str = "v1_structural_only"
    notes: tuple[str, ...] = (
        "V1 elastic and seismic inputs are not reinterpreted as V2 structural physics.",
        "The original V1 runner remains available for exact V1 regression behavior.",
    )


def migrate_v1_to_v2(scenario: ScenarioSpec) -> V1Migration:
    """Map only V1 structural and explicit porosity inputs into GeoSpec V2."""
    structures: list[dict[str, object]] = []
    if scenario.fold:
        structures.append(
            {
                "kind": "fold",
                "id": "legacy_fold",
                "amplitude_m": scenario.fold.amplitude_m,
                "wavelength_m": scenario.fold.wavelength_m,
                "phase_deg": scenario.fold.phase_deg,
                "x_origin_m": 0.0,
            }
        )
    if scenario.fault:
        structures.append(
            {
                "kind": "fault",
                "id": "legacy_fault",
                "x_position_m": scenario.fault.x_position_m,
                "reference_depth_m": scenario.fault.reference_depth_m,
                "dip_deg": scenario.fault.dip_degrees,
                "dip_direction": "positive_x",
                "throw_m": scenario.fault.throw_m,
                "displacement": "normal",
                "displaced_side": (
                    "positive_x" if scenario.fault.downthrown_side == "right" else "negative_x"
                ),
            }
        )

    label_to_code: dict[str, int] = {}
    target_layer = scenario.co2_change.target_layer if scenario.co2_change else None
    layers: list[dict[str, object]] = []
    for index, layer in enumerate(scenario.layers):
        code = label_to_code.setdefault(layer.lithology, len(label_to_code) + 1)
        facies_id = f"facies_{code}_{_slug_id(layer.lithology, 'facies')}"
        layers.append(
            {
                "id": f"layer_{index + 1}_{_slug_id(layer.name, 'layer')}",
                "name": layer.name.replace("_", " ").title(),
                "facies_id": facies_id,
                "thickness_m": layer.thickness_m,
                "porosity_fraction": layer.porosity,
                "is_reservoir": layer.name == target_layer,
            }
        )

    payload = {
        "schema_version": "2.0",
        "metadata": {
            "name": f"{scenario.name}_v1_structural",
            "description": f"Structural-only V2 migration of V1 scenario: {scenario.description}",
        },
        "seed": scenario.seed,
        "grid": {
            "nx": scenario.grid.nx,
            "ndepth": scenario.grid.nz,
            "dx_m": scenario.grid.dx_m,
            "ddepth_m": scenario.grid.dz_m,
            "x_origin_m": 0.0,
            "depth_origin_m": 0.0,
        },
        "facies": [
            {
                "id": f"facies_{code}_{_slug_id(label, 'facies')}",
                "code": code,
                "label": label,
            }
            for label, code in label_to_code.items()
        ],
        "layers": layers,
        "structures": structures,
        "structural_method": {
            "method_id": "analytic_source_depth_v1",
            "operation_order": "listed",
            "boundary_behavior": "clip_to_grid",
        },
        "outputs": {
            "save_arrays": True,
            "save_dataset_metadata": True,
            "save_diagnostic_figure": True,
        },
        "assumptions": [
            *scenario.assumptions,
            "Compatibility migration preserves only explicit V1 geometry and porosity.",
        ],
    }
    return V1Migration(spec=GeoSpecV2.model_validate(payload))
