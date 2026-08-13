"""Small structural correctness diagnostic for the semantic World workflow."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from geoworld_open.domains.geoscience.structural import StructuralWorldResult
from geoworld_open.viz.export import save_figure
from geoworld_open.viz.overlays import draw_region_boundary
from geoworld_open.viz.spatial import attach_colorbar, plot_spatial_field
from geoworld_open.viz.style import FigurePreset, get_preset, style_context


def save_structural_world_diagnostic(
    result: StructuralWorldResult,
    path: str | Path,
    *,
    preset: str | FigurePreset = "compact",
    vertical_exaggeration: float = 2.0,
) -> Path:
    """Plot structural outputs without recomputing or mutating scientific fields."""
    selected = get_preset(preset)
    dataset = result.dataset
    x = np.asarray(dataset.coords["x"].values, dtype=float)
    depth = np.asarray(dataset.coords["depth"].values, dtype=float)
    facies_labels = {item.code: item.label for item in result.structural_input.facies}
    panels = (
        (
            np.asarray(dataset["facies"].values),
            "A. Categorical facies",
            "facies",
            None,
            facies_labels,
        ),
        (
            np.asarray(dataset["porosity"].values),
            "B. Explicit porosity",
            "porosity",
            "fraction",
            None,
        ),
        (
            np.asarray(dataset["reservoir_selection"].values),
            "C. Reservoir selection",
            "binary_mask",
            None,
            {0: "Outside", 1: "Reservoir"},
        ),
        (
            np.asarray(dataset["structural_displacement_m"].values),
            "D. Signed displacement",
            "signed_displacement",
            "m",
            None,
        ),
    )

    with style_context(selected):
        figure, axes = plt.subplots(
            1,
            4,
            figsize=selected.figure_size(1, 4),
            constrained_layout=True,
        )
        for axis, (values, title, quantity, unit, labels) in zip(axes, panels):
            spatial = plot_spatial_field(
                axis,
                values,
                x=x,
                depth=depth,
                quantity=quantity,
                title=title,
                unit=unit,
                category_labels=labels,
                vertical_exaggeration=vertical_exaggeration,
            )
            if labels:
                ticks = sorted(labels)
                colorbar = attach_colorbar(
                    figure,
                    spatial,
                    axis,
                    ticks=ticks,
                )
                colorbar.ax.set_yticklabels([labels[value] for value in ticks])
            else:
                attach_colorbar(figure, spatial, axis)

            fault_values = (
                dataset.coords["fault"].values if "fault" in dataset.coords else ()
            )
            for fault_id in fault_values:
                draw_region_boundary(
                    axis,
                    x,
                    depth,
                    np.asarray(
                        dataset["fault_selection"].sel(fault=fault_id).values,
                        dtype=bool,
                    ),
                    color="#202020",
                    label=str(fault_id) if axis is axes[0] else None,
                )

        if dataset.sizes.get("fault", 0):
            axes[0].legend(loc="lower left", fontsize=selected.tick_size - 0.5)
        figure.suptitle(
            f"Structural World correctness diagnostic: {result.structural_input.name}",
            fontsize=selected.title_size,
            fontweight="bold",
        )
        return save_figure(figure, path, preset=selected)
