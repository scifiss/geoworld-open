"""Pure analytic structural geology with no World-registry responsibilities."""

from __future__ import annotations

from typing import Any

import numpy as np
import xarray as xr

from geoworld_open.specs import FaultSpec, FoldSpec, GeoSpec


DEPTH_X = ("depth", "x")


def create_structural_grid(spec: GeoSpec) -> xr.Dataset:
    """Create an empty cell-centered grid with authoritative mirrored coordinates."""
    grid = spec.grid
    x = grid.x_origin_m + (np.arange(grid.nx, dtype=float) + 0.5) * grid.dx_m
    depth = grid.depth_origin_m + (
        np.arange(grid.ndepth, dtype=float) + 0.5
    ) * grid.ddepth_m
    dataset = xr.Dataset(coords={"depth": depth, "x": x})
    dataset.coords["depth"].attrs = {
        "units": "m",
        "long_name": "cell-center depth below model datum",
        "positive": "down",
        "axis": "Z",
    }
    dataset.coords["x"].attrs = {
        "units": "m",
        "long_name": "cell-center horizontal coordinate",
        "axis": "X",
    }
    return dataset


def _attrs(
    units: str,
    long_name: str,
    scientific_class: str,
    capability_id: str,
    method_id: str,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "units": units,
        "long_name": long_name,
        "scientific_class": scientific_class,
        "source_capability": capability_id,
        "method_id": method_id,
        **extra,
    }


def compute_structural_geometry(spec: GeoSpec, grid: xr.Dataset) -> tuple[xr.Dataset, dict[str, Any]]:
    """Apply listed fold/fault source-depth transforms exactly once."""
    x = np.asarray(grid.coords["x"].values)
    depth = np.asarray(grid.coords["depth"].values)
    xx, dd = np.meshgrid(x, depth)
    source_depth = dd.copy()
    fold_displacement = np.zeros_like(source_depth)
    fault_displacement = np.zeros_like(source_depth)
    fault_entity_ids: list[str] = []
    fault_selections: list[np.ndarray] = []
    fault_diagnostics: list[dict[str, Any]] = []

    for structure in spec.structures:
        if isinstance(structure, FoldSpec):
            phase_rad = np.deg2rad(structure.phase_deg)
            displacement = structure.amplitude_m * np.sin(
                2.0 * np.pi * (xx - structure.x_origin_m) / structure.wavelength_m
                + phase_rad
            )
            source_depth -= displacement
            fold_displacement += displacement
            continue

        assert isinstance(structure, FaultSpec)
        direction = 1.0 if structure.dip_direction == "positive_x" else -1.0
        trace_x = structure.x_position_m + direction * (
            source_depth - structure.reference_depth_m
        ) / np.tan(np.deg2rad(structure.dip_deg))
        selection = (
            xx >= trace_x
            if structure.displaced_side == "positive_x"
            else xx <= trace_x
        )
        signed_throw = (
            structure.throw_m if structure.displacement == "normal" else -structure.throw_m
        )
        source_depth[selection] -= signed_throw
        fault_displacement[selection] += signed_throw
        fault_entity_id = f"fault:{structure.id}"
        fault_entity_ids.append(fault_entity_id)
        fault_selections.append(selection)
        fault_diagnostics.append(
            {
                "fault_entity_id": fault_entity_id,
                "dip_deg": structure.dip_deg,
                "dip_direction": structure.dip_direction,
                "displacement": structure.displacement,
                "displaced_side": structure.displaced_side,
                "throw_m": structure.throw_m,
                "selected_cell_count": int(np.count_nonzero(selection)),
            }
        )

    depth_min = spec.grid.depth_origin_m
    depth_max = depth_min + spec.grid.thickness_m
    clipped = (source_depth < depth_min) | (source_depth >= depth_max)
    source_depth = np.clip(source_depth, depth_min, np.nextafter(depth_max, depth_min))
    combined_displacement = dd - source_depth
    stacked_faults = (
        np.stack(fault_selections).astype(bool)
        if fault_selections
        else np.empty((0, spec.grid.ndepth, spec.grid.nx), dtype=bool)
    )
    capability_id = "structural_geometry"
    method_id = spec.structural_method.method_id
    fragment = xr.Dataset(
        data_vars={
            "source_depth_m": (
                DEPTH_X,
                source_depth,
                _attrs("m", "source depth", "computational_field", capability_id, method_id),
            ),
            "structural_displacement_m": (
                DEPTH_X,
                combined_displacement,
                _attrs(
                    "m", "total structural displacement", "derived_scientific_field",
                    capability_id, method_id,
                ),
            ),
            "fold_displacement_m": (
                DEPTH_X,
                fold_displacement,
                _attrs(
                    "m", "cumulative fold displacement", "derived_scientific_field",
                    capability_id, method_id,
                ),
            ),
            "fault_displacement_m": (
                DEPTH_X,
                fault_displacement,
                _attrs(
                    "m", "cumulative signed fault throw", "derived_scientific_field",
                    capability_id, method_id,
                ),
            ),
            "fault_selection": (
                ("fault", "depth", "x"),
                stacked_faults,
                _attrs(
                    "1", "displaced-side selection by Fault Entity",
                    "derived_scientific_field", capability_id, method_id,
                    boolean_meaning="true means the cell is on the explicitly displaced side",
                ),
            ),
            "boundary_clipped_mask": (
                DEPTH_X,
                clipped.astype(bool),
                _attrs(
                    "1", "source-depth clipping diagnostic", "diagnostic_field",
                    capability_id, method_id,
                ),
            ),
        },
        coords={
            "depth": grid.coords["depth"],
            "x": grid.coords["x"],
            "fault": fault_entity_ids,
        },
    )
    fragment.coords["fault"].attrs = {
        "units": "1",
        "long_name": "persistent Fault Entity identifier",
    }
    return fragment, {
        "structure_count": len(spec.structures),
        "fault_count": len(fault_entity_ids),
        "clipped_cell_count": int(np.count_nonzero(clipped)),
        "operation_order": [structure.id for structure in spec.structures],
        "faults": fault_diagnostics,
    }


def assign_stratigraphic_fields(
    spec: GeoSpec,
    dataset: xr.Dataset,
) -> tuple[xr.Dataset, dict[str, Any]]:
    """Assign explicit formation, facies, porosity, and reservoir-role values."""
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
    porosities = np.asarray(
        [layer.porosity_fraction for layer in spec.layers], dtype=float
    )
    reservoir_roles = np.asarray([layer.is_reservoir for layer in spec.layers], dtype=bool)
    facies = facies_codes[layer_index]
    porosity = porosities[layer_index]
    reservoir_selection = reservoir_roles[layer_index]
    facies_map = {item.code: item.id for item in spec.facies}
    flag_values = sorted(facies_map)
    capability_id = "stratigraphic_assignment"
    method_id = "explicit_layer_lookup_v1"
    coords = {"depth": dataset.coords["depth"], "x": dataset.coords["x"]}
    fragment = xr.Dataset(
        data_vars={
            "layer_index": (
                DEPTH_X,
                layer_index,
                _attrs(
                    "1", "zero-based explicit Formation index", "computational_field",
                    capability_id, method_id,
                    formation_entity_ids=[f"formation:{layer.id}" for layer in spec.layers],
                ),
            ),
            "facies": (
                DEPTH_X,
                facies,
                _attrs(
                    "1", "categorical facies code", "scientific_state_field",
                    capability_id, method_id,
                    flag_values=flag_values,
                    flag_meanings=" ".join(facies_map[value] for value in flag_values),
                ),
            ),
            "porosity": (
                DEPTH_X,
                porosity,
                _attrs(
                    "1", "explicit bulk-volume pore fraction", "scientific_state_field",
                    capability_id, method_id,
                ),
            ),
            "reservoir_selection": (
                DEPTH_X,
                reservoir_selection.astype(bool),
                _attrs(
                    "1", "selection of cells from formations with explicit reservoir role",
                    "derived_scientific_field", capability_id, method_id,
                    boolean_meaning="true means source material has explicit reservoir role",
                ),
            ),
        },
        coords=coords,
    )
    return fragment, {
        "formation_count": len(spec.layers),
        "facies_codes": flag_values,
        "reservoir_cell_count": int(np.count_nonzero(reservoir_selection)),
    }
