import numpy as np

import xarray as xr

from geoworld_open.data import (
    DIMENSION_ORDER,
    assign_standard_coordinate,
    validate_coordinate_conventions,
)
from geoworld_open.science import run_structural_workflow


def test_xarray_coordinates_and_metadata(structural_v2_scenario) -> None:
    dataset = run_structural_workflow(structural_v2_scenario).dataset
    assert tuple(dataset["facies"].dims) == ("depth", "x")
    assert dataset.sizes["depth"] == structural_v2_scenario.grid.ndepth
    assert dataset.sizes["x"] == structural_v2_scenario.grid.nx
    assert np.all(np.diff(dataset.coords["depth"]) > 0)
    assert np.all(np.diff(dataset.coords["x"]) > 0)
    assert dataset.coords["depth"].attrs["units"] == "m"
    assert dataset.coords["depth"].attrs["positive"] == "down"
    assert dataset.coords["x"].attrs["units"] == "m"
    validate_coordinate_conventions(dataset)


def test_variables_are_aligned_and_masks_are_boolean(structural_v2_scenario) -> None:
    dataset = run_structural_workflow(structural_v2_scenario).dataset
    for name in ("facies", "layer_index", "porosity", "reservoir_mask"):
        assert dataset[name].dims == ("depth", "x")
        assert dataset[name].attrs["source_operator"]
        assert dataset[name].attrs["method_id"]
        assert dataset[name].attrs["physical_meaning"]
    assert dataset["reservoir_mask"].dtype == np.dtype(bool)
    assert dataset["fault_mask"].dtype == np.dtype(bool)
    assert dataset["boundary_clipped_mask"].dtype == np.dtype(bool)
    assert dataset["facies"].attrs["flag_meanings"] == "shale sand"


def test_phase2_does_not_synthesize_later_physics(structural_v2_scenario) -> None:
    dataset = run_structural_workflow(structural_v2_scenario).dataset
    forbidden = {"vp_m_s", "vs_m_s", "density_kg_m3", "seismic", "reflectivity"}
    assert forbidden.isdisjoint(dataset.data_vars)
    assert DIMENSION_ORDER == ("realization", "vintage", "angle", "time", "depth", "x")


def test_future_coordinate_conventions_are_representable() -> None:
    dataset = xr.Dataset()
    dataset = assign_standard_coordinate(dataset, "vintage", ["baseline", "monitor"])
    dataset = assign_standard_coordinate(dataset, "time", [0.0, 0.002, 0.004])
    dataset = assign_standard_coordinate(dataset, "angle", [5.0, 15.0, 25.0])
    dataset = assign_standard_coordinate(dataset, "realization", [0, 1])
    assert dataset.coords["time"].attrs["units"] == "s"
    assert dataset.coords["angle"].attrs["units"] == "degree"
    assert dataset.coords["vintage"].attrs["units"] == "1"
    assert dataset.coords["realization"].attrs["units"] == "1"
