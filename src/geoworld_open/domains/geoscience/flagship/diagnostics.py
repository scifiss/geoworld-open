"""Bounded correctness figure for the flagship demonstration."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from geoworld_open.domains.geoscience.flagship.integration import FlagshipWorldResult


def save_flagship_diagnostic(
    result: FlagshipWorldResult,
    path: str | Path,
) -> Path:
    structural = result.structural_dataset
    baseline = result.baseline_dataset
    perturbed = result.perturbed_dataset
    x = np.asarray(structural.coords["x"])
    depth = np.asarray(structural.coords["depth"])
    extent = (x[0], x[-1], depth[-1], depth[0])
    panels = (
        (structural["facies"], "Facies", "viridis"),
        (structural["porosity"], "Porosity", "viridis"),
        (baseline["pressure"] / 1.0e6, "Baseline pressure (MPa)", "viridis"),
        (
            perturbed["pressure_perturbation"] / 1.0e6,
            "Analytic pressure change (MPa)",
            "magma",
        ),
        (perturbed["pressure"] / 1.0e6, "Perturbed pressure (MPa)", "viridis"),
        (baseline["temperature"], "Temperature (degC)", "plasma"),
    )
    figure, axes = plt.subplots(2, 3, figsize=(12, 6), constrained_layout=True)
    for axis, (values, title, cmap) in zip(axes.flat, panels):
        image = axis.imshow(values, extent=extent, aspect="auto", cmap=cmap)
        axis.axvline(result.flagship_input.well.x_m, color="white", linewidth=1.0)
        axis.scatter(
            [result.flagship_input.well.x_m] * len(result.observation_rows),
            [item.sample_depth_m for item in result.observation_rows],
            s=12,
            color="black",
        )
        axis.set_title(title)
        axis.set_xlabel("x (m)")
        axis.set_ylabel("depth (m)")
        figure.colorbar(image, ax=axis, shrink=0.8)
    figure.suptitle("Flagship synthetic World correctness diagnostic")
    output = Path(path)
    figure.savefig(output, dpi=150)
    plt.close(figure)
    return output
