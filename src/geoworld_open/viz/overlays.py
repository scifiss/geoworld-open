"""Domain-neutral semantic overlays for spatial scientific panels."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np


def draw_fault_trace(
    axis: plt.Axes,
    x: np.ndarray,
    depth: np.ndarray,
    *,
    label: str = "Fault",
    color: str = "#c0392b",
) -> None:
    axis.plot(x, depth, color=color, linewidth=1.5, linestyle="--", label=label, zorder=5)


def draw_well_trajectory(
    axis: plt.Axes,
    x: np.ndarray,
    depth: np.ndarray,
    *,
    label: str = "Well",
    color: str = "#111827",
) -> None:
    axis.plot(x, depth, color=color, linewidth=1.8, label=label, zorder=6)


def draw_observation_locations(
    axis: plt.Axes,
    x: np.ndarray,
    depth: np.ndarray,
    *,
    label: str = "Observation",
    color: str = "#f59e0b",
) -> None:
    axis.scatter(
        x,
        depth,
        s=28,
        marker="o",
        facecolor=color,
        edgecolor="white",
        linewidth=0.7,
        label=label,
        zorder=7,
    )


def draw_region_boundary(
    axis: plt.Axes,
    x: np.ndarray,
    depth: np.ndarray,
    mask: np.ndarray,
    *,
    color: str = "#ffffff",
    label: str | None = None,
) -> None:
    axis.contour(
        x,
        depth,
        np.asarray(mask, dtype=float),
        levels=[0.5],
        colors=[color],
        linewidths=1.1,
    )
    if label:
        axis.plot([], [], color=color, linewidth=1.1, label=label)
