import numpy as np

from geoworld_open.workflow import run_workflow


def test_workflow_is_array_deterministic(layered_scenario) -> None:
    first = run_workflow(layered_scenario)
    second = run_workflow(layered_scenario)
    assert first.arrays.keys() == second.arrays.keys()
    for name in first.arrays:
        np.testing.assert_array_equal(first.arrays[name], second.arrays[name])


def test_expected_scientific_outputs(layered_scenario) -> None:
    result = run_workflow(layered_scenario)
    expected = {
        "porosity",
        "saturation",
        "vp_m_s",
        "vs_m_s",
        "density_kg_m3",
        "acoustic_impedance",
        "normal_reflectivity",
        "synthetic_seismic",
        "avo_reflectivity_gather",
        "avo_stack_low",
        "avo_stack_mid",
        "avo_stack_high",
    }
    assert expected <= result.arrays.keys()
    assert result.arrays["vp_m_s"].shape == (100, 160)
    assert result.arrays["avo_reflectivity_gather"].shape == (8, 100, 160)
    assert np.isfinite(result.arrays["avo_reflectivity_gather"]).all()


def test_co2_change_is_confined_to_target_layer(co2_scenario) -> None:
    result = run_workflow(co2_scenario)
    mask = result.arrays["co2_change_mask"].astype(bool)
    target = next(i for i, layer in enumerate(co2_scenario.layers) if layer.name == "storage_sand")
    assert mask.any()
    assert np.all(result.arrays["layer_index"][mask] == target)
    assert np.all(result.arrays["saturation"][mask] == 0.60)

