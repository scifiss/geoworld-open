"""Compact public summary figure."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from geoworld_open.workflow import WorkflowResult


def _plot(ax: plt.Axes, data: np.ndarray, title: str, extent: list[float], cmap: str) -> None:
    image = ax.imshow(data, aspect="auto", extent=extent, origin="upper", cmap=cmap)
    ax.set_title(title, fontsize=9)
    ax.set_xlabel("x (m)", fontsize=8)
    ax.set_ylabel("depth (m)", fontsize=8)
    ax.tick_params(labelsize=7)
    plt.colorbar(image, ax=ax, fraction=0.046, pad=0.025)


def save_summary_figure(result: WorkflowResult, path: str | Path) -> None:
    arrays = result.arrays
    scenario = result.scenario
    width = scenario.grid.nx * scenario.grid.dx_m
    depth = scenario.grid.nz * scenario.grid.dz_m
    extent = [0.0, width, depth, 0.0]
    candidates = [
        ("layer_index", "Layer index", "tab20"),
        ("porosity", "Porosity", "viridis"),
        ("saturation", "Fluid saturation", "magma"),
        ("vp_m_s", "Vp (m/s)", "viridis"),
        ("vs_m_s", "Vs (m/s)", "viridis"),
        ("density_kg_m3", "Density (kg/m3)", "cividis"),
        ("acoustic_impedance", "Acoustic impedance", "viridis"),
        ("normal_reflectivity", "Normal reflectivity", "seismic"),
        ("synthetic_seismic", "Synthetic seismic", "seismic"),
    ]
    stack_keys = sorted(key for key in arrays if key.startswith("avo_stack_"))
    candidates.extend((key, key.replace("avo_stack_", "AVO ").replace("_", " ").title(), "seismic") for key in stack_keys[:3])

    figure, axes = plt.subplots(3, 4, figsize=(13, 8), constrained_layout=True)
    for ax, (key, title, cmap) in zip(axes.flat, candidates):
        _plot(ax, arrays[key], title, extent, cmap)
    for ax in axes.flat[len(candidates) :]:
        ax.axis("off")
    figure.suptitle(f"GeoWorld Open: {scenario.name}", fontsize=13)
    figure.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(figure)

