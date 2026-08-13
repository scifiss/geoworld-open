"""Bounded correctness figure for the flagship demonstration."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from geoworld_open.domains.geoscience.flagship.figures import (
    _intersecting_fault_mask,
)
from geoworld_open.domains.geoscience.flagship.integration import FlagshipWorldResult
from geoworld_open.viz.colormaps import shared_limits
from geoworld_open.viz.export import save_figure
from geoworld_open.viz.overlays import (
    draw_observation_locations,
    draw_region_boundary,
    draw_well_trajectory,
)
from geoworld_open.viz.spatial import attach_colorbar, plot_spatial_field
from geoworld_open.viz.style import FigurePreset, get_preset, style_context


def _add_diagnostic_context(
    axis: plt.Axes,
    result: FlagshipWorldResult,
    *,
    x: np.ndarray,
    depth: np.ndarray,
) -> None:
    fault_selection, persistent_fault_id = _intersecting_fault_mask(result)
    draw_region_boundary(
        axis,
        x,
        depth,
        fault_selection,
        color="#b91c1c",
        label=f"Fault ({persistent_fault_id})",
    )
    draw_region_boundary(
        axis,
        x,
        depth,
        np.asarray(result.structural_dataset["reservoir_selection"].values, dtype=bool),
        color="#f8fafc",
        label="Reservoir region",
    )
    well = result.flagship_input.well
    draw_well_trajectory(
        axis,
        np.asarray([well.x_m, well.x_m]),
        np.asarray([well.top_depth_m, well.bottom_depth_m]),
        label=well.label,
    )
    draw_observation_locations(
        axis,
        np.asarray([item.sampled_x_m for item in result.observation_rows]),
        np.asarray([item.sampled_depth_m for item in result.observation_rows]),
        label="Pressure evidence",
    )


def save_flagship_diagnostic(
    result: FlagshipWorldResult,
    path: str | Path,
    *,
    preset: str | FigurePreset = "compact",
    vertical_exaggeration: float = 2.0,
) -> Path:
    """Render a semantic correctness diagnostic without changing scientific fields."""
    selected = get_preset(preset)
    structural = result.structural_dataset
    baseline = result.baseline_dataset
    perturbed = result.perturbed_dataset
    x = np.asarray(structural.coords["x"].values, dtype=float)
    depth = np.asarray(structural.coords["depth"].values, dtype=float)
    baseline_pressure = np.asarray(baseline["pressure"].values, dtype=float) / 1.0e6
    perturbed_pressure = np.asarray(perturbed["pressure"].values, dtype=float) / 1.0e6
    pressure_change = (
        np.asarray(perturbed["pressure_perturbation"].values, dtype=float) / 1.0e6
    )
    pressure_limits = shared_limits(baseline_pressure, perturbed_pressure)
    perturbation_limits = shared_limits(pressure_change, include_zero=True)
    facies_labels = {
        item.code: item.label for item in result.flagship_input.structural.facies
    }
    panels = (
        (
            np.asarray(structural["facies"].values),
            "A. Facies",
            "facies",
            None,
            None,
        ),
        (
            np.asarray(structural["porosity"].values),
            "B. Porosity",
            "porosity",
            "fraction",
            None,
        ),
        (
            baseline_pressure,
            "C. Baseline pressure",
            "pressure",
            "MPa",
            pressure_limits,
        ),
        (
            pressure_change,
            "D. Analytic pressure perturbation",
            "positive_perturbation",
            "MPa",
            perturbation_limits,
        ),
        (
            perturbed_pressure,
            "E. Perturbed pressure",
            "pressure",
            "MPa",
            pressure_limits,
        ),
        (
            np.asarray(baseline["temperature"].values, dtype=float),
            "F. Temperature",
            "temperature",
            "degC",
            None,
        ),
    )

    with style_context(selected):
        figure, axes = plt.subplots(
            2,
            3,
            figsize=selected.figure_size(2, 3),
            constrained_layout=True,
        )
        for axis, (values, title, quantity, unit, limits) in zip(axes.flat, panels):
            spatial = plot_spatial_field(
                axis,
                values,
                x=x,
                depth=depth,
                quantity=quantity,
                title=title,
                unit=unit,
                limits=limits,
                category_labels=facies_labels if quantity == "facies" else None,
                vertical_exaggeration=vertical_exaggeration,
            )
            _add_diagnostic_context(axis, result, x=x, depth=depth)
            if quantity == "facies":
                codes = sorted(facies_labels)
                colorbar = attach_colorbar(
                    figure,
                    spatial,
                    axis,
                    label="Facies",
                    ticks=codes,
                )
                colorbar.ax.set_yticklabels([facies_labels[code] for code in codes])
            else:
                attach_colorbar(figure, spatial, axis)
        axes.flat[0].legend(loc="lower left", fontsize=selected.tick_size - 0.5)
        figure.suptitle(
            "Flagship synthetic World correctness diagnostic",
            fontsize=selected.title_size,
            fontweight="bold",
        )
        return save_figure(figure, path, preset=selected)
