"""Consistent figure export and resource cleanup."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from geoworld_open.viz.style import FigurePreset, get_preset


def save_figure(
    figure: Figure,
    path: str | Path,
    *,
    preset: str | FigurePreset = "compact",
    dpi: int | None = None,
    transparent: bool = False,
    close: bool = True,
) -> Path:
    output = Path(path)
    if output.suffix.lower() not in {".png", ".svg"}:
        raise ValueError("figure output must use .png or .svg")
    output.parent.mkdir(parents=True, exist_ok=True)
    selected = get_preset(preset)
    figure.savefig(
        output,
        dpi=dpi or selected.dpi,
        transparent=transparent,
        bbox_inches="tight",
        facecolor="none" if transparent else "white",
    )
    if close:
        plt.close(figure)
    return output
