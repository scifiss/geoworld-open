"""Generic 2-D x/depth plotting with explicit geometry semantics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colorbar import Colorbar
from matplotlib.image import AxesImage

from geoworld_open.viz.colormaps import (
    QuantityStyle,
    categorical_cmap,
    display_norm,
    quantity_style,
)


@dataclass(frozen=True)
class SpatialImage:
    image: AxesImage
    style: QuantityStyle
    limits: tuple[float, float]
    unit: str | None
    colorbar_label: str


def _colorbar_label(style: QuantityStyle, unit: str | None) -> str:
    if style.categorical:
        return style.label
    resolved_unit = unit if unit is not None else style.default_unit
    if not resolved_unit or resolved_unit in {"1", "fraction"}:
        return style.label
    return f"{style.label} ({resolved_unit})"


def cell_edges(centers: np.ndarray) -> np.ndarray:
    values = np.asarray(centers, dtype=float)
    if values.ndim != 1 or values.size == 0:
        raise ValueError("cell centers must be a nonempty one-dimensional array")
    if values.size == 1:
        return np.asarray([values[0] - 0.5, values[0] + 0.5])
    differences = np.diff(values)
    if not np.all(differences > 0):
        raise ValueError("cell centers must be strictly increasing")
    midpoints = values[:-1] + differences / 2.0
    return np.concatenate(
        ([values[0] - differences[0] / 2.0], midpoints, [values[-1] + differences[-1] / 2.0])
    )


def cell_center_extent(x: np.ndarray, depth: np.ndarray) -> tuple[float, float, float, float]:
    x_edges = cell_edges(x)
    depth_edges = cell_edges(depth)
    return x_edges[0], x_edges[-1], depth_edges[-1], depth_edges[0]


def plot_spatial_field(
    axis: plt.Axes,
    values: np.ndarray,
    *,
    x: np.ndarray,
    depth: np.ndarray,
    quantity: str,
    title: str,
    unit: str | None = None,
    limits: tuple[float, float] | None = None,
    category_labels: Mapping[int, str] | None = None,
    vertical_exaggeration: float = 1.0,
) -> SpatialImage:
    array = np.asarray(values)
    if array.shape != (len(depth), len(x)):
        raise ValueError("spatial field shape must be (depth, x)")
    if vertical_exaggeration <= 0:
        raise ValueError("vertical exaggeration must be positive")
    style = quantity_style(quantity)
    norm = display_norm(array, style, limits=limits)
    cmap = (
        categorical_cmap(
            category_labels or np.unique(array[np.isfinite(array)]),
            palette=style.cmap_name,
        )
        if style.categorical
        else style.cmap()
    )
    image = axis.imshow(
        np.ma.masked_invalid(array),
        extent=cell_center_extent(np.asarray(x), np.asarray(depth)),
        origin="upper",
        interpolation="nearest",
        aspect=vertical_exaggeration,
        cmap=cmap,
        norm=norm,
    )
    axis.set_title(title, loc="left", fontweight="bold")
    axis.set_xlabel("x (m)")
    axis.set_ylabel("depth (m)")
    axis.grid(False)
    if vertical_exaggeration != 1.0:
        axis.text(
            0.99,
            0.02,
            f"VE {vertical_exaggeration:g}×",
            transform=axis.transAxes,
            ha="right",
            va="bottom",
            fontsize="x-small",
            color="#374151",
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.8, "pad": 1.5},
        )
    resolved_limits = (float(norm.vmin), float(norm.vmax))
    resolved_unit = unit if unit is not None else style.default_unit
    return SpatialImage(
        image=image,
        style=style,
        limits=resolved_limits,
        unit=resolved_unit,
        colorbar_label=_colorbar_label(style, unit),
    )


def attach_colorbar(
    figure: plt.Figure,
    spatial: SpatialImage,
    axis: plt.Axes | list[plt.Axes] | np.ndarray,
    *,
    colorbar_axis: plt.Axes | None = None,
    label: str | None = None,
    ticks: list[float] | None = None,
    fraction: float = 0.046,
    pad: float = 0.025,
) -> Colorbar:
    colorbar = figure.colorbar(
        spatial.image,
        ax=None if colorbar_axis is not None else axis,
        cax=colorbar_axis,
        fraction=fraction,
        pad=pad,
        ticks=ticks,
    )
    colorbar.set_label(label or spatial.colorbar_label)
    return colorbar
