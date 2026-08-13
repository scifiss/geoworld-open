"""Public-facing composition for the flagship synthetic World."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

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


def _intersecting_fault_mask(
    result: FlagshipWorldResult,
) -> tuple[np.ndarray, str]:
    structural = result.structural_dataset
    persistent_fault_id = (
        f"fault:{result.flagship_input.reservoir_region.intersecting_fault_id}"
    )
    available = {str(value) for value in structural.coords["fault"].values.tolist()}
    if persistent_fault_id not in available:
        raise ValueError(
            f"authored intersecting fault {persistent_fault_id!r} is absent from "
            f"fault_selection coordinates {sorted(available)}"
        )
    mask = structural["fault_selection"].sel(fault=persistent_fault_id)
    return np.asarray(mask.values, dtype=bool), persistent_fault_id


def _add_spatial_context(
    axis: plt.Axes,
    result: FlagshipWorldResult,
    *,
    x: np.ndarray,
    depth: np.ndarray,
    show_observations: bool = False,
) -> None:
    structural = result.structural_dataset
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
        np.asarray(structural["reservoir_selection"].values, dtype=bool),
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
    if show_observations:
        draw_observation_locations(
            axis,
            np.asarray([item.sampled_x_m for item in result.observation_rows]),
            np.asarray([item.sampled_depth_m for item in result.observation_rows]),
            label="Pressure evidence",
        )


def save_flagship_public_figure(
    result: FlagshipWorldResult,
    path: str | Path,
    *,
    preset: str | FigurePreset = "publication",
) -> Path:
    """Render the flagship story without recomputing or mutating scientific fields."""
    selected = get_preset(preset)
    structural = result.structural_dataset
    baseline = result.baseline_dataset
    perturbed = result.perturbed_dataset
    x = np.asarray(structural.coords["x"].values, dtype=float)
    depth = np.asarray(structural.coords["depth"].values, dtype=float)
    facies = np.asarray(structural["facies"].values)
    porosity = np.asarray(structural["porosity"].values)
    baseline_pressure = np.asarray(baseline["pressure"].values, dtype=float) / 1.0e6
    pressure_change = (
        np.asarray(perturbed["pressure_perturbation"].values, dtype=float) / 1.0e6
    )
    perturbed_pressure = np.asarray(perturbed["pressure"].values, dtype=float) / 1.0e6
    pressure_limits = shared_limits(baseline_pressure, perturbed_pressure)
    delta_limits = shared_limits(pressure_change, include_zero=True)
    facies_labels = {
        item.code: item.label for item in result.flagship_input.structural.facies
    }

    with style_context(selected):
        figure = plt.figure(
            figsize=(
                selected.figure_size(2, 3)[0],
                selected.figure_size(2, 3)[1] + 0.65,
            ),
            constrained_layout=True,
        )
        grid = figure.add_gridspec(3, 3, height_ratios=(0.16, 1.0, 1.0))
        header = figure.add_subplot(grid[0, :])
        header.axis("off")
        header.text(
            0.5,
            0.78,
            "GeoWorld Open | Faulted reservoir state and synthetic evidence",
            ha="center",
            va="center",
            fontsize=selected.title_size,
            fontweight="bold",
        )
        header.text(
            0.5,
            0.18,
            "Analytic synthetic pressure benchmark; not reservoir-flow simulation or history matching. Spatial panels use VE 2×.",
            ha="center",
            va="center",
            fontsize=selected.subtitle_size,
            color="#4b5563",
        )
        axes = [
            figure.add_subplot(grid[row + 1, column])
            for row in range(2)
            for column in range(3)
        ]

        facies_image = plot_spatial_field(
            axes[0],
            facies,
            x=x,
            depth=depth,
            quantity="facies",
            title="A. Geological structure",
            category_labels=facies_labels,
            vertical_exaggeration=2.0,
        )
        _add_spatial_context(
            axes[0], result, x=x, depth=depth, show_observations=True
        )
        facies_codes = sorted(facies_labels)
        facies_colorbar = attach_colorbar(
            figure,
            facies_image,
            axes[0],
            label="Facies",
            ticks=facies_codes,
        )
        facies_colorbar.ax.set_yticklabels([facies_labels[code] for code in facies_codes])
        axes[0].legend(loc="lower left", fontsize=selected.tick_size - 0.5)

        porosity_image = plot_spatial_field(
            axes[1],
            porosity,
            x=x,
            depth=depth,
            quantity="porosity",
            title="B. Porosity",
            unit="fraction",
            vertical_exaggeration=2.0,
        )
        _add_spatial_context(axes[1], result, x=x, depth=depth)
        attach_colorbar(figure, porosity_image, axes[1], label="Porosity (fraction)")

        baseline_image = plot_spatial_field(
            axes[2],
            baseline_pressure,
            x=x,
            depth=depth,
            quantity="pressure",
            title="C. Baseline pressure",
            unit="MPa",
            limits=pressure_limits,
            vertical_exaggeration=2.0,
        )
        _add_spatial_context(axes[2], result, x=x, depth=depth)

        delta_image = plot_spatial_field(
            axes[3],
            pressure_change,
            x=x,
            depth=depth,
            quantity="positive_perturbation",
            title="D. Analytic pressure perturbation",
            unit="MPa",
            limits=delta_limits,
            vertical_exaggeration=2.0,
        )
        _add_spatial_context(axes[3], result, x=x, depth=depth)
        attach_colorbar(figure, delta_image, axes[3], label="Δpressure (MPa)")

        perturbed_image = plot_spatial_field(
            axes[4],
            perturbed_pressure,
            x=x,
            depth=depth,
            quantity="pressure",
            title="E. Perturbed pressure",
            unit="MPa",
            limits=pressure_limits,
            vertical_exaggeration=2.0,
        )
        _add_spatial_context(
            axes[4], result, x=x, depth=depth, show_observations=True
        )
        pressure_colorbar_axis = axes[2].inset_axes((1.03, 0.0, 0.035, 1.0))
        pressure_colorbar_axis.set_in_layout(False)
        attach_colorbar(
            figure,
            baseline_image,
            [axes[2], axes[4]],
            colorbar_axis=pressure_colorbar_axis,
            label="Pressure (MPa), shared scale",
        )

        requested_depth = np.asarray(
            [item.requested_depth_m for item in result.observation_rows], dtype=float
        )
        sampled_depth = np.asarray(
            [item.sampled_depth_m for item in result.observation_rows], dtype=float
        )
        model_pressure = np.asarray(
            [item.true_model_pressure_pa for item in result.observation_rows], dtype=float
        ) / 1.0e6
        observed_pressure = np.asarray(
            [item.observed_pressure_pa for item in result.observation_rows], dtype=float
        ) / 1.0e6
        axes[5].plot(
            model_pressure,
            sampled_depth,
            marker="o",
            color="#2563eb",
            label="Model at sampled cell",
        )
        axes[5].scatter(
            observed_pressure,
            sampled_depth,
            marker="D",
            s=34,
            color="#d97706",
            edgecolor="white",
            linewidth=0.7,
            label="Synthetic evidence",
            zorder=4,
        )
        for requested, sampled, pressure in zip(
            requested_depth, sampled_depth, observed_pressure
        ):
            if not np.isclose(requested, sampled):
                axes[5].annotate(
                    f"requested {requested:g} m",
                    xy=(pressure, sampled),
                    xytext=(5, 5),
                    textcoords="offset points",
                    fontsize=selected.tick_size - 1,
                    color="#4b5563",
                )
        axes[5].invert_yaxis()
        axes[5].set_title(
            "F. Synthetic Well-pressure evidence",
            loc="left",
            fontweight="bold",
        )
        axes[5].set_xlabel("Pressure (MPa)")
        axes[5].set_ylabel("Sampled depth (m)")
        axes[5].grid(True, axis="x")
        axes[5].legend(loc="best")

        return save_figure(figure, path, preset=selected)
