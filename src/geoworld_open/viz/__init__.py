"""Professional, reusable scientific visualization helpers."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

from geoworld_open.viz.colormaps import (
    MISSING_COLOR,
    QUANTITY_STYLES,
    QuantityStyle,
    categorical_cmap,
    categorical_norm,
    display_norm,
    finite_limits,
    quantity_style,
    shared_limits,
    symmetric_limits,
)
from geoworld_open.viz.export import save_figure
from geoworld_open.viz.overlays import (
    draw_fault_trace,
    draw_observation_locations,
    draw_region_boundary,
    draw_well_trajectory,
)
from geoworld_open.viz.spatial import (
    attach_colorbar,
    cell_center_extent,
    cell_edges,
    plot_spatial_field,
)
from geoworld_open.viz.style import PRESETS, FigurePreset, get_preset, style_context
from geoworld_open.viz.summary import (
    PanelSpec,
    SUMMARY_PRESETS,
    available_summary_panels,
    resolve_summary_panels,
    save_summary_figure,
)

__all__ = [
    "MISSING_COLOR",
    "PRESETS",
    "QUANTITY_STYLES",
    "SUMMARY_PRESETS",
    "FigurePreset",
    "PanelSpec",
    "QuantityStyle",
    "attach_colorbar",
    "available_summary_panels",
    "categorical_cmap",
    "categorical_norm",
    "cell_center_extent",
    "cell_edges",
    "display_norm",
    "draw_fault_trace",
    "draw_observation_locations",
    "draw_region_boundary",
    "draw_well_trajectory",
    "finite_limits",
    "get_preset",
    "plot_spatial_field",
    "quantity_style",
    "resolve_summary_panels",
    "save_figure",
    "save_summary_figure",
    "shared_limits",
    "style_context",
    "symmetric_limits",
]
