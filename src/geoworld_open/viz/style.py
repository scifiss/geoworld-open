"""Reusable, scoped Matplotlib style presets for public scientific figures."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass

import matplotlib as mpl


@dataclass(frozen=True)
class FigurePreset:
    """A compact set of figure conventions without global rcParam mutation."""

    name: str
    panel_size: tuple[float, float]
    dpi: int
    title_size: float
    subtitle_size: float
    axis_label_size: float
    tick_size: float
    line_width: float
    grid_alpha: float

    def figure_size(self, rows: int, columns: int) -> tuple[float, float]:
        return self.panel_size[0] * columns, self.panel_size[1] * rows


PRESETS: dict[str, FigurePreset] = {
    "compact": FigurePreset("compact", (3.45, 2.55), 160, 12, 9, 8, 7, 1.2, 0.16),
    "publication": FigurePreset(
        "publication", (3.7, 2.8), 300, 13, 9.5, 8.5, 7.5, 1.25, 0.14
    ),
    "presentation": FigurePreset(
        "presentation", (4.7, 3.4), 180, 17, 12, 11, 9.5, 1.7, 0.18
    ),
}


def get_preset(name: str | FigurePreset = "compact") -> FigurePreset:
    if isinstance(name, FigurePreset):
        return name
    try:
        return PRESETS[name]
    except KeyError as exc:
        raise ValueError(
            f"unknown figure preset {name!r}; choose from {sorted(PRESETS)}"
        ) from exc


def style_context(
    preset: str | FigurePreset = "compact",
) -> AbstractContextManager[None]:
    """Return a local rc context; callers never mutate process-wide styling."""
    selected = get_preset(preset)
    return mpl.rc_context(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Liberation Sans"],
            "axes.titlesize": selected.subtitle_size,
            "axes.labelsize": selected.axis_label_size,
            "axes.linewidth": 0.7,
            "axes.edgecolor": "#364152",
            "axes.labelcolor": "#202936",
            "xtick.labelsize": selected.tick_size,
            "ytick.labelsize": selected.tick_size,
            "xtick.color": "#4b5563",
            "ytick.color": "#4b5563",
            "grid.color": "#9ca3af",
            "grid.alpha": selected.grid_alpha,
            "grid.linewidth": 0.45,
            "lines.linewidth": selected.line_width,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "savefig.dpi": selected.dpi,
            "figure.dpi": 110,
            "legend.frameon": False,
            "legend.fontsize": selected.tick_size,
        }
    )
