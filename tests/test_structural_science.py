import numpy as np
import pytest

from geoworld_open.domains.geoscience.structural.numerics import (
    assign_stratigraphic_fields,
    compute_structural_geometry,
    create_structural_grid,
)
from geoworld_open.specs import GeoSpec


def _spec(structures=None) -> GeoSpec:
    return GeoSpec.model_validate(
        {
            "schema_version": "2.0",
            "metadata": {"name": "structural_test", "description": "test model"},
            "seed": 17,
            "grid": {"nx": 30, "ndepth": 24, "dx_m": 10.0, "ddepth_m": 5.0},
            "facies": [
                {"id": "shale", "code": 1, "label": "Shale"},
                {"id": "sand", "code": 2, "label": "Sand"},
            ],
            "layers": [
                {
                    "id": "upper_shale", "name": "Upper shale", "facies_id": "shale",
                    "thickness_m": 40.0, "porosity_fraction": 0.08,
                    "is_reservoir": False,
                },
                {
                    "id": "sand", "name": "Reservoir sand", "facies_id": "sand",
                    "thickness_m": 40.0, "porosity_fraction": 0.24,
                    "is_reservoir": True,
                },
                {
                    "id": "lower_shale", "name": "Lower shale", "facies_id": "shale",
                    "thickness_m": 40.0, "porosity_fraction": 0.10,
                    "is_reservoir": False,
                },
            ],
            "structures": structures or [],
            "structural_method": {
                "method_id": "analytic_source_depth_v1",
                "operation_order": "listed",
                "boundary_behavior": "clip_to_grid",
            },
            "outputs": {},
            "assumptions": ["Synthetic structural test."],
        }
    )


def _fault(**overrides):
    payload = {
        "kind": "fault",
        "id": "fault_a",
        "x_position_m": 150.0,
        "reference_depth_m": 60.0,
        "dip_deg": 60.0,
        "dip_direction": "positive_x",
        "throw_m": 10.0,
        "displacement": "normal",
        "displaced_side": "positive_x",
    }
    payload.update(overrides)
    return payload


def _fold(**overrides):
    payload = {
        "kind": "fold",
        "id": "fold_a",
        "amplitude_m": 10.0,
        "wavelength_m": 200.0,
        "phase_deg": 30.0,
        "x_origin_m": 0.0,
    }
    payload.update(overrides)
    return payload


def test_horizontal_layers_and_identity_source_depth() -> None:
    spec = _spec()
    geometry, _ = compute_structural_geometry(spec, create_structural_grid(spec))
    expected = np.broadcast_to(
        geometry.coords["depth"].values[:, None], geometry["source_depth_m"].shape
    )
    np.testing.assert_array_equal(geometry["source_depth_m"], expected)
    np.testing.assert_array_equal(geometry["structural_displacement_m"], 0.0)
    assert geometry.sizes["fault"] == 0
    assert not geometry["boundary_clipped_mask"].any()


def test_fold_amplitude_and_phase_follow_declared_sinusoid() -> None:
    spec = _spec([_fold()])
    geometry, _ = compute_structural_geometry(spec, create_structural_grid(spec))
    x = geometry.coords["x"].values
    expected = 10.0 * np.sin(2.0 * np.pi * x / 200.0 + np.deg2rad(30.0))
    np.testing.assert_allclose(geometry["fold_displacement_m"][0], expected, atol=1e-12)
    np.testing.assert_allclose(
        geometry["fold_displacement_m"],
        np.broadcast_to(expected, geometry["fold_displacement_m"].shape),
        atol=1e-12,
    )


@pytest.mark.parametrize("displacement, expected", [("normal", 10.0), ("reverse", -10.0)])
def test_fault_displacement_sign(displacement: str, expected: float) -> None:
    spec = _spec([_fault(displacement=displacement)])
    geometry, _ = compute_structural_geometry(spec, create_structural_grid(spec))
    selected = geometry["fault_selection"].sel(fault="fault:fault_a")
    values = np.unique(geometry["fault_displacement_m"].values[selected.values])
    np.testing.assert_array_equal(values, np.asarray([expected]))


@pytest.mark.parametrize("dip_direction", ["positive_x", "negative_x"])
@pytest.mark.parametrize("displaced_side", ["positive_x", "negative_x"])
def test_fault_dip_and_selected_side_are_explicit(
    dip_direction: str,
    displaced_side: str,
) -> None:
    spec = _spec([_fault(dip_direction=dip_direction, displaced_side=displaced_side)])
    geometry, _ = compute_structural_geometry(spec, create_structural_grid(spec))
    x = geometry.coords["x"].values
    depth = geometry.coords["depth"].values
    xx, dd = np.meshgrid(x, depth)
    direction = 1.0 if dip_direction == "positive_x" else -1.0
    trace_x = 150.0 + direction * (dd - 60.0) / np.tan(np.deg2rad(60.0))
    expected = xx >= trace_x if displaced_side == "positive_x" else xx <= trace_x
    np.testing.assert_array_equal(
        geometry["fault_selection"].sel(fault="fault:fault_a"), expected
    )


def test_listed_structure_order_is_deterministic_and_material() -> None:
    fold_then_fault = _spec([_fold(), _fault()])
    fault_then_fold = _spec([_fault(), _fold()])
    first, diagnostics = compute_structural_geometry(
        fold_then_fault, create_structural_grid(fold_then_fault)
    )
    repeated, _ = compute_structural_geometry(
        fold_then_fault, create_structural_grid(fold_then_fault)
    )
    second, _ = compute_structural_geometry(
        fault_then_fold, create_structural_grid(fault_then_fold)
    )
    np.testing.assert_array_equal(first["source_depth_m"], repeated["source_depth_m"])
    assert not np.array_equal(first["fault_selection"], second["fault_selection"])
    assert diagnostics["operation_order"] == ["fold_a", "fault_a"]


def test_source_depth_clipping_is_explicitly_diagnosed() -> None:
    spec = _spec([_fold(amplitude_m=25.0, phase_deg=90.0, wavelength_m=1000.0)])
    geometry, diagnostics = compute_structural_geometry(spec, create_structural_grid(spec))
    assert geometry["boundary_clipped_mask"].any()
    assert diagnostics["clipped_cell_count"] > 0
    assert float(geometry["source_depth_m"].min()) == 0.0


def test_facies_porosity_and_reservoir_role_follow_deformed_source_depth() -> None:
    spec = _spec([_fault()])
    geometry, _ = compute_structural_geometry(spec, create_structural_grid(spec))
    fields, _ = assign_stratigraphic_fields(spec, geometry)
    boundaries = np.asarray([40.0, 80.0, 120.0])
    expected_layer = np.searchsorted(boundaries, geometry["source_depth_m"], side="right")
    expected_layer = np.clip(expected_layer, 0, 2)
    np.testing.assert_array_equal(fields["layer_index"], expected_layer)
    np.testing.assert_array_equal(fields["facies"], np.asarray([1, 2, 1])[expected_layer])
    np.testing.assert_allclose(fields["porosity"], np.asarray([0.08, 0.24, 0.10])[expected_layer])
    np.testing.assert_array_equal(
        fields["reservoir_selection"], np.asarray([False, True, False])[expected_layer]
    )
