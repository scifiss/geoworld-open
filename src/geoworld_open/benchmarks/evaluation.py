"""Numerical tolerance and deterministic reproducibility evaluation."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from geoworld_open.benchmarks.models import NumericalComparison, ReproducibilityEvaluation
from geoworld_open.benchmarks.runner import run_benchmark


def compare_numerical_outputs(
    left_dir: str | Path,
    right_dir: str | Path,
    *,
    rtol: float = 0.0,
    atol: float = 0.0,
) -> NumericalComparison:
    left = Path(left_dir)
    right = Path(right_dir)
    left_arrays = {item.relative_to(left).as_posix(): item for item in left.rglob("*.npy")}
    right_arrays = {item.relative_to(right).as_posix(): item for item in right.rglob("*.npy")}
    issues: list[str] = []
    if set(left_arrays) != set(right_arrays):
        issues.append("numerical artifact sets differ")
    compared: list[str] = []
    exact = True
    max_error = 0.0
    for name in sorted(set(left_arrays) & set(right_arrays)):
        first = np.load(left_arrays[name], allow_pickle=False)
        second = np.load(right_arrays[name], allow_pickle=False)
        compared.append(name)
        if first.shape != second.shape or first.dtype != second.dtype:
            issues.append(f"shape or dtype mismatch: {name}")
            exact = False
            continue
        if not np.array_equal(first, second, equal_nan=True):
            exact = False
        if np.issubdtype(first.dtype, np.number):
            finite = np.isfinite(first) & np.isfinite(second)
            if finite.any():
                max_error = max(max_error, float(np.max(np.abs(first[finite] - second[finite]))))
            if not np.allclose(first, second, rtol=rtol, atol=atol, equal_nan=True):
                issues.append(f"numerical tolerance exceeded: {name}")
        elif not np.array_equal(first, second):
            issues.append(f"array mismatch: {name}")
    return NumericalComparison(
        matches=not issues,
        exact=exact and not issues,
        compared_arrays=tuple(compared),
        max_absolute_error=max_error,
        issues=tuple(issues),
    )


def evaluate_reproducibility(
    benchmark_id: str,
    output_root: str | Path,
    *,
    rtol: float = 0.0,
    atol: float = 0.0,
) -> ReproducibilityEvaluation:
    root = Path(output_root)
    first = run_benchmark(benchmark_id, root / "run-1")
    second = run_benchmark(benchmark_id, root / "run-2")
    numerical = compare_numerical_outputs(first.output_dir, second.output_dir, rtol=rtol, atol=atol)
    return ReproducibilityEvaluation(
        benchmark_id=benchmark_id,
        first=first,
        second=second,
        numerical=numerical,
    )
