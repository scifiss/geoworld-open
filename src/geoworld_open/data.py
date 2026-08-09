"""Coordinate-aware scientific dataset conventions for GeoWorld Open."""

from __future__ import annotations

from typing import Final

import numpy as np
import xarray as xr

from geoworld_open.specs.models import GeoSpecV2


DIMENSION_ORDER: Final = ("realization", "vintage", "angle", "time", "depth", "x")
COORDINATE_UNITS: Final = {
    "x": "m",
    "depth": "m",
    "time": "s",
    "angle": "degree",
    "vintage": "1",
    "realization": "1",
    "fault": "1",
}
COORDINATE_LONG_NAMES: Final = {
    "x": "cell-center horizontal coordinate",
    "depth": "cell-center depth below model datum",
    "time": "two-way seismic sample time",
    "angle": "PP incidence angle",
    "vintage": "survey or model state identifier",
    "realization": "ensemble realization identifier",
    "fault": "explicit fault identifier",
}


def assign_standard_coordinate(
    dataset: xr.Dataset,
    name: str,
    values: np.ndarray | list[object],
) -> xr.Dataset:
    """Assign one recognized coordinate with stable scientific metadata."""
    if name not in COORDINATE_UNITS:
        raise ValueError(f"unknown standard coordinate {name!r}")
    array = np.asarray(values)
    if array.ndim != 1 or array.size == 0:
        raise ValueError(f"coordinate {name!r} must be a non-empty one-dimensional array")
    if name in {"x", "depth", "time", "angle"} and not np.all(np.diff(array.astype(float)) > 0):
        raise ValueError(f"coordinate {name!r} must be strictly increasing")
    if len(set(array.tolist())) != array.size:
        raise ValueError(f"coordinate {name!r} values must be unique")
    result = dataset.assign_coords({name: array})
    result.coords[name].attrs = {
        "units": COORDINATE_UNITS[name],
        "long_name": COORDINATE_LONG_NAMES[name],
    }
    if name == "depth":
        result.coords[name].attrs.update({"axis": "Z", "positive": "down"})
    elif name == "x":
        result.coords[name].attrs["axis"] = "X"
    elif name == "time":
        result.coords[name].attrs["axis"] = "T"
    return result


def create_earth_dataset(spec: GeoSpecV2) -> xr.Dataset:
    """Create an empty cell-centered Earth-model dataset with physical coordinates."""
    grid = spec.grid
    x = grid.x_origin_m + (np.arange(grid.nx, dtype=float) + 0.5) * grid.dx_m
    depth = grid.depth_origin_m + (np.arange(grid.ndepth, dtype=float) + 0.5) * grid.ddepth_m
    dataset = assign_standard_coordinate(xr.Dataset(), "depth", depth)
    dataset = assign_standard_coordinate(dataset, "x", x)
    dataset.attrs = {
        "schema_version": spec.schema_version,
        "scenario_name": spec.metadata.name,
        "coordinate_convention": "cell_centered_cartesian_depth_positive_down",
    }
    return dataset


def validate_coordinate_conventions(dataset: xr.Dataset) -> None:
    """Reject datasets that violate public coordinate and mask conventions."""
    for name in ("x", "depth"):
        if name not in dataset.coords:
            raise ValueError(f"dataset is missing required coordinate {name!r}")
        values = np.asarray(dataset.coords[name].values)
        if values.ndim != 1 or values.size == 0 or not np.all(np.diff(values) > 0):
            raise ValueError(f"coordinate {name!r} must be one-dimensional and strictly increasing")
        expected_units = COORDINATE_UNITS[name]
        if dataset.coords[name].attrs.get("units") != expected_units:
            raise ValueError(f"coordinate {name!r} must use units {expected_units!r}")

    for name, variable in dataset.data_vars.items():
        if name.endswith("_mask") and variable.dtype != np.dtype(bool):
            raise ValueError(f"scientific mask {name!r} must have Boolean dtype")
        for attr in ("units", "long_name", "physical_meaning", "method_id", "source_operator"):
            if attr not in variable.attrs:
                raise ValueError(f"variable {name!r} is missing metadata attribute {attr!r}")
