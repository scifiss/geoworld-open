from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pytest
from matplotlib.colors import BoundaryNorm, TwoSlopeNorm

from geoworld_open.domains.geoscience.flagship import (
    load_flagship_spec,
    run_flagship_world,
)
from geoworld_open.domains.geoscience.flagship.figures import (
    save_flagship_public_figure,
)
from geoworld_open.viz import (
    MISSING_COLOR,
    PRESETS,
    SUMMARY_PRESETS,
    available_summary_panels,
    display_norm,
    plot_spatial_field,
    quantity_style,
    resolve_summary_panels,
    save_summary_figure,
    shared_limits,
)
from geoworld_open.workflow import run_workflow


ROOT = Path(__file__).resolve().parents[1]
FLAGSHIP = ROOT / "examples" / "scenarios" / "flagship_faulted_reservoir.yaml"


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

    missing_rgba = quantity_style("pressure").cmap()(np.ma.masked)
    np.testing.assert_allclose(missing_rgba, mpl.colors.to_rgba(MISSING_COLOR))


def test_pressure_comparison_limits_are_shared() -> None:
    baseline = np.asarray([[1.0, np.nan], [2.0, 3.0]])
    perturbed = np.asarray([[1.5, np.nan], [2.5, 4.0]])
    assert shared_limits(baseline, perturbed) == (1.0, 4.0)


def test_spatial_plot_uses_cell_centers_and_does_not_mutate_values() -> None:
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
        physical_aspect=True,
        vertical_exaggeration=2.0,
    )
    assert spatial.image.get_extent() == [0.0, 20.0, 10.0, 0.0]
    np.testing.assert_array_equal(values, before)
    plt.close(figure)


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
