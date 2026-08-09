"""Minimal Phase 2 structural diagnostic visualization."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import BoundaryNorm, ListedColormap

from geoworld_open.engine.execution import ScientificWorkflowResult


def save_structural_diagnostic(result: ScientificWorkflowResult, path: str | Path) -> None:
    dataset = result.dataset
    x = np.asarray(dataset.coords["x"])
    depth = np.asarray(dataset.coords["depth"])
    dx = result.spec.grid.dx_m
    dd = result.spec.grid.ddepth_m
    extent = [x[0] - dx / 2, x[-1] + dx / 2, depth[-1] + dd / 2, depth[0] - dd / 2]
    figure, axes = plt.subplots(1, 4, figsize=(14, 3.8), constrained_layout=True)

    facies_values = sorted(int(value) for value in np.unique(dataset["facies"]))
    colors = plt.get_cmap("tab20")(np.linspace(0.05, 0.95, max(len(facies_values), 2)))
    facies_cmap = ListedColormap(colors[: len(facies_values)])
    bounds = [facies_values[0] - 0.5, *[value + 0.5 for value in facies_values]]
    facies_image = axes[0].imshow(
        dataset["facies"], origin="upper", extent=extent, aspect="auto",
        cmap=facies_cmap, norm=BoundaryNorm(bounds, facies_cmap.N),
    )
    facies_bar = figure.colorbar(facies_image, ax=axes[0], ticks=facies_values, fraction=0.046)
    facies_bar.set_label("facies code")

    porosity_image = axes[1].imshow(
        dataset["porosity"], origin="upper", extent=extent, aspect="auto", cmap="viridis",
        vmin=0.0, vmax=max(0.01, float(dataset["porosity"].max())),
    )
    figure.colorbar(porosity_image, ax=axes[1], fraction=0.046, label="fraction")

    reservoir_image = axes[2].imshow(
        dataset["reservoir_mask"], origin="upper", extent=extent, aspect="auto",
        cmap=ListedColormap(["#f4f4f4", "#1f77b4"]), vmin=0, vmax=1,
    )
    figure.colorbar(reservoir_image, ax=axes[2], fraction=0.046, ticks=[0, 1], label="mask")

    displacement = dataset["structural_displacement_m"]
    limit = max(1.0, float(np.max(np.abs(displacement))))
    displacement_image = axes[3].imshow(
        displacement, origin="upper", extent=extent, aspect="auto", cmap="RdBu_r",
        vmin=-limit, vmax=limit,
    )
    figure.colorbar(displacement_image, ax=axes[3], fraction=0.046, label="m")

    if dataset.sizes.get("fault", 0):
        combined_fault = dataset["fault_mask"].any(dim="fault")
        for ax in axes:
            ax.contour(x, depth, combined_fault, levels=[0.5], colors="#202020", linewidths=0.65)

    for ax, title in zip(
        axes,
        ("Facies and faults", "Explicit porosity", "Reservoir mask", "Structural displacement"),
    ):
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("x (m)")
        ax.set_ylabel("depth (m)")
        ax.tick_params(labelsize=8)
    figure.suptitle(f"GeoWorld Open Phase 2 structural diagnostic: {result.spec.metadata.name}")
    figure.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(figure)
