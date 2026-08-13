from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pytest
from matplotlib.colors import BoundaryNorm, TwoSlopeNorm

from geoworld_open.domains.geoscience.flagship import (
    FlagshipSpec,
    FlagshipWorldResult,
    load_flagship_spec,
    run_flagship_world,
)
from geoworld_open.domains.geoscience.flagship.figures import (
    _intersecting_fault_mask,
    save_flagship_public_figure,
)
from geoworld_open.domains.geoscience.flagship.diagnostics import (
    save_flagship_diagnostic,
)
from geoworld_open.domains.geoscience.structural import run_structural_world
from geoworld_open.specs import load_geospec
from geoworld_open.viz import (
    MISSING_COLOR,
    PRESETS,
    SUMMARY_PRESETS,
    attach_colorbar,
    available_summary_panels,
    display_norm,
    plot_spatial_field,
    quantity_style,
    resolve_summary_panels,
    save_summary_figure,
    shared_limits,
)
from geoworld_open.workflow import run_workflow
from geoworld_open.world_diagnostics import save_structural_world_diagnostic


ROOT = Path(__file__).resolve().parents[1]
FLAGSHIP = ROOT / "examples" / "scenarios" / "flagship_faulted_reservoir.yaml"
STRUCTURAL = ROOT / "examples" / "scenarios" / "structural_multifault.yaml"


def test_summary_api_is_backward_compatible_bounded_and_discoverable(
    layered_scenario,
    tmp_path,
) -> None:
    result = run_workflow(layered_scenario)
    available = available_summary_panels(result)
    selected = resolve_summary_panels(result)

    assert set(PRESETS) == {"compact", "presentation", "publication"}
    assert set(SUMMARY_PRESETS) == {
        "compact",
        "full",
        "properties",
        "seismic",
        "structure",
    }
    assert 4 <= len(selected) <= 6
    assert len(selected) < len(available)

    output = save_summary_figure(
        result,
        tmp_path / "selected.png",
        panels=("porosity", "synthetic_seismic"),
    )
    assert output.is_file()
    assert output.stat().st_size > 0


def test_invalid_summary_panel_or_preset_fails_clearly(layered_scenario) -> None:
    result = run_workflow(layered_scenario)
    with pytest.raises(ValueError, match="unavailable"):
        resolve_summary_panels(result, ("not_a_field",))
    with pytest.raises(ValueError, match="unknown summary preset"):
        resolve_summary_panels(result, "not_a_preset")


def test_quantity_normalization_is_semantic_and_missing_values_are_neutral() -> None:
    categorical = display_norm(
        np.asarray([[1, 2], [2, 1]]),
        quantity_style("facies"),
    )
    signed = display_norm(
        np.asarray([[-0.25, 0.1], [0.5, -0.2]]),
        quantity_style("reflectivity"),
    )
    assert isinstance(categorical, BoundaryNorm)
    assert isinstance(signed, TwoSlopeNorm)
    assert signed.vcenter == 0.0
    assert signed.vmin == -signed.vmax
    positive = display_norm(
        np.asarray([[0.25, 0.5]]),
        quantity_style("positive_perturbation"),
    )
    assert positive.vmin == 0.0
    all_zero_positive = display_norm(
        np.zeros((2, 2)),
        quantity_style("positive_perturbation"),
    )
    assert all_zero_positive.vmin == 0.0
    assert all_zero_positive.vmax > 0.0

    missing_rgba = quantity_style("pressure").cmap()(np.ma.masked)
    np.testing.assert_allclose(missing_rgba, mpl.colors.to_rgba(MISSING_COLOR))


def test_pressure_comparison_limits_are_shared() -> None:
    baseline = np.asarray([[1.0, np.nan], [2.0, 3.0]])
    perturbed = np.asarray([[1.5, np.nan], [2.5, 4.0]])
    assert shared_limits(baseline, perturbed) == (1.0, 4.0)


def test_spatial_plot_uses_cell_centers_explicit_ve_and_units_without_mutation() -> None:
    values = np.asarray([[1.0, np.nan], [2.0, 3.0]])
    before = values.copy()
    figure, axis = plt.subplots()
    spatial = plot_spatial_field(
        axis,
        values,
        x=np.asarray([5.0, 15.0]),
        depth=np.asarray([2.5, 7.5]),
        quantity="pressure",
        title="Pressure",
        vertical_exaggeration=2.0,
    )
    assert spatial.image.get_extent() == [0.0, 20.0, 10.0, 0.0]
    assert spatial.image.axes.get_aspect() == 2.0
    assert [item.get_text() for item in axis.texts] == ["VE 2×"]
    assert spatial.colorbar_label == "Pressure (MPa)"
    colorbar = attach_colorbar(figure, spatial, axis)
    assert colorbar.ax.get_ylabel() == "Pressure (MPa)"
    np.testing.assert_array_equal(values, before)
    plt.close(figure)


def test_dimensionless_and_categorical_colorbar_labels_do_not_claim_units() -> None:
    figure, axes = plt.subplots(1, 2)
    coordinates = np.asarray([0.5, 1.5])
    porosity = plot_spatial_field(
        axes[0],
        np.asarray([[0.1, 0.2], [0.2, 0.1]]),
        x=coordinates,
        depth=coordinates,
        quantity="porosity",
        title="Porosity",
        unit="fraction",
    )
    facies = plot_spatial_field(
        axes[1],
        np.asarray([[1, 2], [2, 1]]),
        x=coordinates,
        depth=coordinates,
        quantity="facies",
        title="Facies",
        unit="1",
    )
    assert porosity.colorbar_label == "Porosity"
    assert facies.colorbar_label == "Facies"
    plt.close(figure)


def test_summary_default_and_override_never_use_automatic_aspect(
    layered_scenario,
    tmp_path,
    monkeypatch,
) -> None:
    import geoworld_open.viz.summary as summary_module

    result = run_workflow(layered_scenario)
    original = summary_module.plot_spatial_field
    seen: list[float] = []

    def recording_plot(*args, **kwargs):
        seen.append(kwargs["vertical_exaggeration"])
        return original(*args, **kwargs)

    monkeypatch.setattr(summary_module, "plot_spatial_field", recording_plot)
    save_summary_figure(result, tmp_path / "default.png")
    assert set(seen) == {2.0}

    seen.clear()
    save_summary_figure(
        result,
        tmp_path / "physical.png",
        panels=("porosity",),
        vertical_exaggeration=1.0,
    )
    assert seen == [1.0]


def test_flagship_selects_authored_intersecting_fault_not_first_fault() -> None:
    payload = load_flagship_spec(FLAGSHIP).model_dump(mode="python")
    payload["structural"]["structures"].insert(
        1,
        {
            "kind": "fault",
            "id": "decoy_fault",
            "x_position_m": 1350.0,
            "reference_depth_m": 250.0,
            "dip_deg": 55.0,
            "dip_direction": "negative_x",
            "throw_m": 15.0,
            "displacement": "normal",
            "displaced_side": "negative_x",
        },
    )
    result = run_flagship_world(FlagshipSpec.model_validate(payload))
    faults = result.structural_dataset.coords["fault"].values.tolist()
    assert faults == ["fault:decoy_fault", "fault:fault_f1"]

    selected, persistent_fault_id = _intersecting_fault_mask(result)
    assert persistent_fault_id == "fault:fault_f1"
    np.testing.assert_array_equal(
        selected,
        result.structural_dataset["fault_selection"].sel(fault="fault:fault_f1"),
    )
    assert not np.array_equal(
        selected,
        result.structural_dataset["fault_selection"].isel(fault=0),
    )


def test_flagship_missing_authored_fault_fails_clearly(monkeypatch) -> None:
    result = run_flagship_world(load_flagship_spec(FLAGSHIP))
    missing_fault = result.structural_dataset.sel(fault=[])
    monkeypatch.setattr(
        FlagshipWorldResult,
        "structural_dataset",
        property(lambda _result: missing_fault),
    )
    with pytest.raises(ValueError, match="authored intersecting fault.*is absent"):
        _intersecting_fault_mask(result)


def test_summary_and_flagship_figures_are_headless_and_immutable(
    layered_scenario,
    tmp_path,
) -> None:
    workflow_result = run_workflow(layered_scenario)
    workflow_before = {
        key: value.copy() for key, value in workflow_result.arrays.items()
    }
    summary = save_summary_figure(workflow_result, tmp_path / "summary.svg")
    assert summary.is_file()
    for key, before in workflow_before.items():
        np.testing.assert_array_equal(workflow_result.arrays[key], before)

    flagship_result = run_flagship_world(load_flagship_spec(FLAGSHIP))
    snapshots = {
        "facies": np.asarray(flagship_result.structural_dataset["facies"]).copy(),
        "porosity": np.asarray(flagship_result.structural_dataset["porosity"]).copy(),
        "baseline": np.asarray(flagship_result.baseline_dataset["pressure"]).copy(),
        "perturbed": np.asarray(flagship_result.perturbed_dataset["pressure"]).copy(),
    }
    public_figure = save_flagship_public_figure(
        flagship_result,
        tmp_path / "flagship_public.png",
        preset="compact",
    )
    assert public_figure.is_file()
    assert public_figure.stat().st_size > 0
    np.testing.assert_array_equal(
        flagship_result.structural_dataset["facies"], snapshots["facies"]
    )
    np.testing.assert_array_equal(
        flagship_result.structural_dataset["porosity"], snapshots["porosity"]
    )
    np.testing.assert_array_equal(
        flagship_result.baseline_dataset["pressure"], snapshots["baseline"]
    )
    np.testing.assert_array_equal(
        flagship_result.perturbed_dataset["pressure"], snapshots["perturbed"]
    )


def test_flagship_diagnostic_uses_semantic_styles_explicit_ve_and_is_immutable(
    tmp_path,
    monkeypatch,
) -> None:
    import geoworld_open.domains.geoscience.flagship.diagnostics as diagnostic_module

    result = run_flagship_world(load_flagship_spec(FLAGSHIP))
    snapshots = {
        "facies": np.asarray(result.structural_dataset["facies"]).copy(),
        "porosity": np.asarray(result.structural_dataset["porosity"]).copy(),
        "baseline": np.asarray(result.baseline_dataset["pressure"]).copy(),
        "perturbed": np.asarray(result.perturbed_dataset["pressure"]).copy(),
        "delta": np.asarray(result.perturbed_dataset["pressure_perturbation"]).copy(),
        "temperature": np.asarray(result.baseline_dataset["temperature"]).copy(),
    }
    original = diagnostic_module.plot_spatial_field
    rendered = []

    def recording_plot(*args, **kwargs):
        spatial = original(*args, **kwargs)
        rendered.append((kwargs, spatial))
        return spatial

    monkeypatch.setattr(diagnostic_module, "plot_spatial_field", recording_plot)
    output = save_flagship_diagnostic(result, tmp_path / "flagship.png")

    assert output.is_file()
    assert [item[0]["quantity"] for item in rendered] == [
        "facies",
        "porosity",
        "pressure",
        "positive_perturbation",
        "pressure",
        "temperature",
    ]
    assert {item[0]["vertical_exaggeration"] for item in rendered} == {2.0}
    assert {item[1].image.axes.get_aspect() for item in rendered} == {2.0}
    assert isinstance(rendered[0][1].image.norm, BoundaryNorm)
    assert rendered[3][1].limits[0] == 0.0
    assert rendered[3][1].limits[1] > 0.0
    assert rendered[2][1].limits == rendered[4][1].limits

    rendered.clear()
    save_flagship_diagnostic(
        result,
        tmp_path / "flagship-physical.png",
        vertical_exaggeration=1.0,
    )
    assert {item[1].image.axes.get_aspect() for item in rendered} == {1.0}
    assert all(not item[1].image.axes.texts for item in rendered)
    for key, before in snapshots.items():
        current = {
            "facies": result.structural_dataset["facies"],
            "porosity": result.structural_dataset["porosity"],
            "baseline": result.baseline_dataset["pressure"],
            "perturbed": result.perturbed_dataset["pressure"],
            "delta": result.perturbed_dataset["pressure_perturbation"],
            "temperature": result.baseline_dataset["temperature"],
        }[key]
        np.testing.assert_array_equal(current, before)


def test_structural_diagnostic_uses_semantic_styles_all_faults_and_is_immutable(
    tmp_path,
    monkeypatch,
) -> None:
    import geoworld_open.world_diagnostics as diagnostic_module

    result = run_structural_world(load_geospec(STRUCTURAL))
    snapshots = {
        name: np.asarray(result.dataset[name]).copy()
        for name in (
            "facies",
            "porosity",
            "reservoir_selection",
            "structural_displacement_m",
            "fault_selection",
        )
    }
    original_plot = diagnostic_module.plot_spatial_field
    original_boundary = diagnostic_module.draw_region_boundary
    rendered = []
    fault_masks = []

    def recording_plot(*args, **kwargs):
        spatial = original_plot(*args, **kwargs)
        rendered.append((kwargs, spatial))
        return spatial

    def recording_boundary(*args, **kwargs):
        fault_masks.append(np.asarray(args[3]).copy())
        return original_boundary(*args, **kwargs)

    monkeypatch.setattr(diagnostic_module, "plot_spatial_field", recording_plot)
    monkeypatch.setattr(diagnostic_module, "draw_region_boundary", recording_boundary)
    output = save_structural_world_diagnostic(result, tmp_path / "structural.png")

    assert output.is_file()
    assert [item[0]["quantity"] for item in rendered] == [
        "facies",
        "porosity",
        "binary_mask",
        "signed_displacement",
    ]
    assert {item[0]["vertical_exaggeration"] for item in rendered} == {2.0}
    assert {item[1].image.axes.get_aspect() for item in rendered} == {2.0}
    assert isinstance(rendered[0][1].image.norm, BoundaryNorm)
    assert isinstance(rendered[2][1].image.norm, BoundaryNorm)
    assert isinstance(rendered[3][1].image.norm, TwoSlopeNorm)
    assert rendered[3][1].limits[0] == -rendered[3][1].limits[1]
    fault_count = result.dataset.sizes["fault"]
    assert len(fault_masks) == len(rendered) * fault_count

    rendered.clear()
    fault_masks.clear()
    save_structural_world_diagnostic(
        result,
        tmp_path / "structural-physical.png",
        vertical_exaggeration=1.0,
    )
    assert {item[1].image.axes.get_aspect() for item in rendered} == {1.0}
    assert all(not item[1].image.axes.texts for item in rendered)
    assert len(fault_masks) == len(rendered) * fault_count
    for name, before in snapshots.items():
        np.testing.assert_array_equal(result.dataset[name], before)
