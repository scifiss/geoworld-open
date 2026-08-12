"""Canonical deterministic workflow for GeoWorld Open."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Iterable

import numpy as np

from geoworld_open.operators import (
    AVOSyntheticOperator,
    AcousticSyntheticOperator,
    ExplicitPropertyOperator,
    LayeredGeologyOperator,
    ScientificOperator,
)
from geoworld_open.schema import ScenarioSpec


@dataclass
class WorkflowResult:
    scenario: ScenarioSpec
    arrays: dict[str, np.ndarray]
    trace: list[dict[str, Any]]


def default_operators() -> list[ScientificOperator]:
    return [
        LayeredGeologyOperator(),
        ExplicitPropertyOperator(),
        AcousticSyntheticOperator(),
        AVOSyntheticOperator(),
    ]


def run_workflow(
    scenario: ScenarioSpec,
    operators: Iterable[ScientificOperator] | None = None,
) -> WorkflowResult:
    """Run each deterministic operator once in a transparent sequence."""
    arrays: dict[str, np.ndarray] = {}
    trace: list[dict[str, Any]] = []
    context: dict[str, Any] = {
        "scenario": scenario,
        "rng": np.random.default_rng(scenario.seed),
    }
    for operator in operators or default_operators():
        started = perf_counter()
        produced = operator.run(arrays, context)
        elapsed_ms = (perf_counter() - started) * 1000.0
        overlap = set(arrays).intersection(produced)
        if overlap:
            raise ValueError(f"operator {operator.metadata.name} overwrote arrays: {sorted(overlap)}")
        arrays.update({name: np.asarray(value) for name, value in produced.items()})
        trace.append(
            {
                "operator": operator.metadata.name,
                "version": operator.metadata.version,
                "description": operator.metadata.description,
                "outputs": sorted(produced),
                "elapsed_ms": round(elapsed_ms, 3),
                "status": "succeeded",
            }
        )
    return WorkflowResult(scenario=scenario, arrays=arrays, trace=trace)
