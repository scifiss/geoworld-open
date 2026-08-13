"""Semantic quantity styles and robust numerical display normalization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import matplotlib as mpl
import numpy as np
from matplotlib.colors import BoundaryNorm, Colormap, ListedColormap, Normalize, TwoSlopeNorm


MISSING_COLOR = "#d9dde3"


@dataclass(frozen=True)
class QuantityStyle:
    quantity: str
    cmap_name: str
    label: str
    default_unit: str | None = None
    centered: bool = False
    categorical: bool = False
    binary: bool = False
    zero_anchored: bool = False

    def cmap(self) -> Colormap:
        return mpl.colormaps[self.cmap_name].with_extremes(bad=MISSING_COLOR)


QUANTITY_STYLES: dict[str, QuantityStyle] = {
    "categorical": QuantityStyle("categorical", "tab20", "Category", categorical=True),
    "facies": QuantityStyle("facies", "tab20", "Facies", categorical=True),
    "lithology": QuantityStyle("lithology", "tab20", "Lithology", categorical=True),
    "porosity": QuantityStyle("porosity", "viridis", "Porosity", "fraction"),
    "saturation": QuantityStyle("saturation", "cividis", "Saturation", "fraction"),
    "vp": QuantityStyle("vp", "viridis", "Vp", "m/s"),
    "vs": QuantityStyle("vs", "magma", "Vs", "m/s"),
    "density": QuantityStyle("density", "cividis", "Density", "kg/m3"),
    "impedance": QuantityStyle("impedance", "plasma", "Acoustic impedance"),
    "pressure": QuantityStyle("pressure", "viridis", "Pressure", "MPa"),
    "temperature": QuantityStyle("temperature", "inferno", "Temperature", "degC"),
    "positive_perturbation": QuantityStyle(
        "positive_perturbation",
        "magma",
        "Positive perturbation",
        zero_anchored=True,
    ),
    "signed_displacement": QuantityStyle(
        "signed_displacement", "RdBu_r", "Signed displacement", centered=True
    ),
    "reflectivity": QuantityStyle(
        "reflectivity", "RdBu_r", "Reflectivity", centered=True
    ),
    "seismic_amplitude": QuantityStyle(
        "seismic_amplitude", "RdBu_r", "Seismic amplitude", centered=True
    ),
    "binary_mask": QuantityStyle(
        "binary_mask", "Greys", "Selection", categorical=True, binary=True
    ),
}


def quantity_style(quantity: str) -> QuantityStyle:
    try:
        return QUANTITY_STYLES[quantity]
    except KeyError as exc:
        raise ValueError(
            f"unknown scientific quantity {quantity!r}; choose from {sorted(QUANTITY_STYLES)}"
        ) from exc


def finite_limits(
    values: np.ndarray | Iterable[np.ndarray],
    *,
    include_zero: bool = False,
) -> tuple[float, float]:
    arrays = (values,) if isinstance(values, np.ndarray) else tuple(values)
    finite = [np.asarray(item, dtype=float)[np.isfinite(item)] for item in arrays]
    nonempty = [item for item in finite if item.size]
    if not nonempty:
        raise ValueError("display limits require at least one finite value")
    combined = np.concatenate(nonempty)
    lower, upper = float(combined.min()), float(combined.max())
    if include_zero:
        lower, upper = min(0.0, lower), max(0.0, upper)
    if lower == upper:
        padding = max(abs(lower) * 0.01, 1.0e-12)
        lower -= padding
        upper += padding
    return lower, upper


def symmetric_limits(values: np.ndarray | Iterable[np.ndarray]) -> tuple[float, float]:
    lower, upper = finite_limits(values)
    bound = max(abs(lower), abs(upper))
    if bound == 0:
        bound = 1.0
    return -bound, bound


def shared_limits(*values: np.ndarray, include_zero: bool = False) -> tuple[float, float]:
    return finite_limits(values, include_zero=include_zero)


def categorical_norm(categories: Iterable[int | float]) -> BoundaryNorm:
    unique = np.asarray(sorted(set(categories)), dtype=float)
    if unique.size == 0:
        raise ValueError("categorical normalization requires at least one category")
    if unique.size == 1:
        boundaries = np.asarray([unique[0] - 0.5, unique[0] + 0.5])
    else:
        midpoints = (unique[:-1] + unique[1:]) / 2.0
        boundaries = np.concatenate(
            ([unique[0] - (midpoints[0] - unique[0])], midpoints, [unique[-1] + (unique[-1] - midpoints[-1])])
        )
    return BoundaryNorm(boundaries, ncolors=max(2, unique.size), clip=False)


def categorical_cmap(
    labels: Mapping[int, str] | Iterable[int],
    *,
    palette: str = "tab20",
) -> ListedColormap:
    keys = sorted(labels) if isinstance(labels, Mapping) else sorted(set(labels))
    if not keys:
        raise ValueError("categorical colormap requires at least one category")
    base = mpl.colormaps[palette]
    color_count = max(2, len(keys))
    colors = [
        base(index / max(1, color_count - 1)) for index in range(color_count)
    ]
    cmap = ListedColormap(colors, name=f"geoworld-{palette}-{len(keys)}")
    return cmap.with_extremes(bad=MISSING_COLOR)


def display_norm(
    values: np.ndarray,
    style: QuantityStyle,
    *,
    limits: tuple[float, float] | None = None,
) -> Normalize:
    if style.categorical:
        finite = np.asarray(values)[np.isfinite(values)]
        categories = (0, 1) if style.binary else np.unique(finite)
        return categorical_norm(categories)
    lower, upper = limits or (
        symmetric_limits(values)
        if style.centered
        else finite_limits(values, include_zero=style.zero_anchored)
    )
    if style.centered:
        bound = max(abs(lower), abs(upper))
        return TwoSlopeNorm(vmin=-bound, vcenter=0.0, vmax=bound)
    return Normalize(vmin=lower, vmax=upper)
