"""Discoverable panel composition for legacy workflow summaries."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np

from geoworld_open.viz.export import save_figure
from geoworld_open.viz.spatial import attach_colorbar, plot_spatial_field
from geoworld_open.viz.style import FigurePreset, get_preset, style_context
from geoworld_open.workflow import WorkflowResult


@dataclass(frozen=True)
class PanelSpec:
    key: str
    title: str
    quantity: str
    unit: str | None = None
    scale: float = 1.0


PANEL_CATALOG: dict[str, PanelSpec] = {
    "layer_index": PanelSpec("layer_index", "Layer index", "categorical"),
    "porosity": PanelSpec("porosity", "Porosity", "porosity", "fraction"),
    "saturation": PanelSpec("saturation", "Fluid saturation", "saturation", "fraction"),
    "vp_m_s": PanelSpec("vp_m_s", "P-wave velocity", "vp", "m/s"),
    "vs_m_s": PanelSpec("vs_m_s", "S-wave velocity", "vs", "m/s"),
    "density_kg_m3": PanelSpec("density_kg_m3", "Density", "density", "kg/m3"),
    "acoustic_impedance": PanelSpec(
        "acoustic_impedance", "Acoustic impedance", "impedance", "kg/(m2 s)"
    ),
    "normal_reflectivity": PanelSpec(
        "normal_reflectivity", "Normal reflectivity", "reflectivity"
    ),
    "synthetic_seismic": PanelSpec(
        "synthetic_seismic", "Synthetic seismic", "seismic_amplitude"
    ),
}


SUMMARY_PRESETS: dict[str, tuple[str, ...]] = {
    "compact": (
        "layer_index",
        "porosity",
        "saturation",
        "vp_m_s",
        "normal_reflectivity",
        "synthetic_seismic",
    ),
    "properties": (
        "porosity",
        "saturation",
        "vp_m_s",
        "vs_m_s",
        "density_kg_m3",
        "acoustic_impedance",
    ),
    "structure": ("layer_index", "porosity", "saturation"),
    "seismic": ("normal_reflectivity", "synthetic_seismic"),
    "full": tuple(PANEL_CATALOG),
}


def _avo_panel(key: str) -> PanelSpec:
    band = key.removeprefix("avo_stack_").replace("_", " ").title()
    return PanelSpec(key, f"AVO {band} stack", "seismic_amplitude")


def available_summary_panels(result: WorkflowResult) -> tuple[PanelSpec, ...]:
    """Return every supported panel actually available in this result."""
    panels = [panel for key, panel in PANEL_CATALOG.items() if key in result.arrays]
    panels.extend(_avo_panel(key) for key in sorted(result.arrays) if key.startswith("avo_stack_"))
    return tuple(panels)


def resolve_summary_panels(
    result: WorkflowResult,
    panels: str | Iterable[str] | None = None,
) -> tuple[PanelSpec, ...]:
    available = {item.key: item for item in available_summary_panels(result)}
    if panels is None:
        requested = SUMMARY_PRESETS["compact"]
    elif isinstance(panels, str):
        if panels not in SUMMARY_PRESETS:
            raise ValueError(
                f"unknown summary preset {panels!r}; choose from {sorted(SUMMARY_PRESETS)}"
            )
        requested = SUMMARY_PRESETS[panels]
        if panels == "full":
            requested = (*requested, *(key for key in available if key.startswith("avo_stack_")))
    else:
        requested = tuple(panels)
    missing = [key for key in requested if key not in available]
    if missing and panels is not None:
        raise ValueError(
            f"summary panels are unavailable: {missing}; available: {sorted(available)}"
        )
    selected = tuple(available[key] for key in requested if key in available)
    if not selected:
        raise ValueError("no supported summary panels are available")
    return selected


def save_summary_figure(
    result: WorkflowResult,
    path: str | Path,
    *,
    panels: str | Iterable[str] | None = None,
    preset: str | FigurePreset = "compact",
) -> Path:
    """Save a bounded, quantity-aware summary while preserving the old import API."""
    selected = resolve_summary_panels(result, panels)
    selected_preset = get_preset(preset)
    columns = min(3, len(selected))
    rows = ceil(len(selected) / columns)
    grid = result.scenario.grid
    x = (np.arange(grid.nx, dtype=float) + 0.5) * grid.dx_m
    depth = (np.arange(grid.nz, dtype=float) + 0.5) * grid.dz_m
    with style_context(selected_preset):
        figure, axes = plt.subplots(
            rows,
            columns,
            figsize=selected_preset.figure_size(rows, columns),
            constrained_layout=True,
            squeeze=False,
        )
        for index, (axis, panel) in enumerate(zip(axes.flat, selected)):
            values = np.asarray(result.arrays[panel.key]) * panel.scale
            category_labels = (
                {layer_index: layer.name for layer_index, layer in enumerate(result.scenario.layers)}
                if panel.key == "layer_index"
                else None
            )
            spatial = plot_spatial_field(
                axis,
                values,
                x=x,
                depth=depth,
                quantity=panel.quantity,
                title=f"{chr(65 + index)}. {panel.title}",
                unit=panel.unit,
                category_labels=category_labels,
            )
            colorbar = attach_colorbar(
                figure,
                spatial,
                axis,
                label=("Layer" if category_labels else panel.unit or spatial.style.label),
                ticks=list(category_labels) if category_labels else None,
            )
            if category_labels:
                colorbar.ax.set_yticklabels(category_labels.values())
        for axis in axes.flat[len(selected) :]:
            axis.set_visible(False)
        figure.suptitle(
            f"GeoWorld Open | {result.scenario.name}",
            fontsize=selected_preset.title_size,
            fontweight="bold",
        )
        return save_figure(figure, path, preset=selected_preset)
