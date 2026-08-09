import numpy as np
import xarray as xr

from geoworld_open.science import run_structural_workflow
from geoworld_open.specs import GeoSpecV2


def _without_structures(spec):
    payload = spec.model_dump(mode="python")
    payload["structures"] = []
    return GeoSpecV2.model_validate(payload)


def test_horizontal_layers_have_exact_cell_assignments(structural_v2_scenario) -> None:
    spec = _without_structures(structural_v2_scenario)
    dataset = run_structural_workflow(spec).dataset
    expected_counts = [30, 26, 28, 36]
    for index, count in enumerate(expected_counts):
        assert int(np.count_nonzero(dataset["layer_index"][:, 0] == index)) == count
    expected = np.broadcast_to(dataset["layer_index"].values[:, :1], dataset["layer_index"].shape)
    np.testing.assert_array_equal(dataset["layer_index"], expected)


def test_fold_free_geometry_is_identity(structural_v2_scenario) -> None:
    dataset = run_structural_workflow(_without_structures(structural_v2_scenario)).dataset
    expected = np.broadcast_to(dataset.coords["depth"].values[:, None], dataset["source_depth_m"].shape)
    np.testing.assert_array_equal(dataset["source_depth_m"], expected)
    assert not dataset["boundary_clipped_mask"].any()
    assert dataset.sizes["fault"] == 0


def test_known_single_normal_fault_has_explicit_throw(structural_v2_scenario) -> None:
    payload = structural_v2_scenario.model_dump(mode="python")
    payload["structures"] = [payload["structures"][1]]
    spec = GeoSpecV2.model_validate(payload)
    dataset = run_structural_workflow(spec).dataset
    selected = dataset["fault_mask"].sel(fault="east_normal_fault")
    assert selected.any()
    assert (~selected).any()
    values = np.unique(dataset["fault_displacement_m"])
    np.testing.assert_array_equal(values, np.array([0.0, 45.0]))
    interior = selected & ~dataset["boundary_clipped_mask"]
    expected = np.broadcast_to(dataset.coords["depth"].values[:, None], selected.shape) - 45.0
    np.testing.assert_allclose(dataset["source_depth_m"].where(interior), np.where(interior, expected, np.nan), equal_nan=True)


def test_multifault_model_is_deterministic_and_integral(structural_v2_scenario) -> None:
    first = run_structural_workflow(structural_v2_scenario)
    second = run_structural_workflow(structural_v2_scenario)
    xr.testing.assert_identical(first.dataset, second.dataset)
    assert list(first.dataset.coords["fault"].values) == ["east_normal_fault", "west_reverse_fault"]
    assert set(np.unique(first.dataset["facies"])) == {1, 2}
    assert set(np.unique(first.dataset["layer_index"])) == {0, 1, 2, 3}
    assert first.dataset["reservoir_mask"].any()
    assert float(first.dataset["fault_displacement_m"].min()) < 0.0
    assert float(first.dataset["fault_displacement_m"].max()) > 0.0
