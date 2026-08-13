"""Run packaged public benchmark cases through supported public workflows."""

from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path

import numpy as np
import yaml

from geoworld_open.benchmarks.models import BenchmarkCase, BenchmarkRun, BenchmarkRunner, BenchmarkSuite
from geoworld_open.sdk import load_manifest, verify_manifest
from geoworld_open.standard import RenderRequest


_DATA_PACKAGE = "geoworld_open.benchmarks.data"


def load_benchmark_suite() -> BenchmarkSuite:
    resource = files(_DATA_PACKAGE).joinpath("suite.yaml")
    payload = yaml.safe_load(resource.read_text(encoding="utf-8"))
    return BenchmarkSuite.model_validate(payload)


def list_benchmarks() -> tuple[BenchmarkCase, ...]:
    return load_benchmark_suite().cases


def benchmark_case(benchmark_id: str) -> BenchmarkCase:
    for case in list_benchmarks():
        if case.benchmark_id == benchmark_id:
            return case
    raise KeyError(f"unknown benchmark: {benchmark_id!r}")


def load_render_benchmark(dimension: str) -> RenderRequest:
    """Load a renderer-neutral public request for ``2d``, ``3d``, or ``4d``."""

    if dimension not in {"2d", "3d", "4d"}:
        raise KeyError(f"unknown render benchmark dimension: {dimension!r}")
    resource = files(_DATA_PACKAGE).joinpath(f"render_{dimension}.yaml")
    return RenderRequest.model_validate(yaml.safe_load(resource.read_text(encoding="utf-8")))


def _run_case(case: BenchmarkCase, input_path: Path, output: Path) -> None:
    if case.runner == BenchmarkRunner.LEGACY:
        from geoworld_open.artifacts import write_artifacts
        from geoworld_open.schema import load_scenario
        from geoworld_open.workflow import run_workflow

        write_artifacts(run_workflow(load_scenario(input_path)), output)
    elif case.runner == BenchmarkRunner.WORLD:
        from geoworld_open.domains.geoscience.structural import run_structural_world
        from geoworld_open.specs import load_geospec
        from geoworld_open.world_artifacts import write_world_artifacts

        write_world_artifacts(run_structural_world(load_geospec(input_path)), output)
    else:
        from geoworld_open.domains.geoscience.flagship import (
            load_flagship_spec,
            run_flagship_world,
            write_flagship_artifacts,
        )

        write_flagship_artifacts(run_flagship_world(load_flagship_spec(input_path)), output)


def _deterministic_hashes(manifest: dict[str, object]) -> tuple[tuple[str, str], ...]:
    hashes: list[tuple[str, str]] = []
    artifacts = manifest.get("artifacts", [])
    if not isinstance(artifacts, list):
        return ()
    for item in artifacts:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            continue
        if item.get("deterministic", True) is False:
            continue
        digest = item.get("sha256")
        if isinstance(digest, str):
            hashes.append((item["path"], digest))
    return tuple(sorted(hashes))


def run_benchmark(benchmark_id: str, output_dir: str | Path) -> BenchmarkRun:
    case = benchmark_case(benchmark_id)
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"benchmark output directory is not empty: {output}")
    resource = files(_DATA_PACKAGE).joinpath(case.input_resource)
    with as_file(resource) as input_path:
        _run_case(case, input_path, output)
    for relative in case.expected_artifacts:
        if not (output / relative).is_file():
            raise ValueError(f"benchmark omitted expected artifact: {relative}")
    for expected in case.expected_arrays:
        array_path = output / expected.path
        if not array_path.is_file():
            raise ValueError(f"benchmark omitted expected array: {expected.path}")
        array = np.load(array_path, allow_pickle=False)
        if array.shape != expected.shape:
            raise ValueError(
                f"benchmark array shape mismatch for {expected.path}: "
                f"{array.shape} != {expected.shape}"
            )
        if str(array.dtype) != expected.dtype:
            raise ValueError(
                f"benchmark array dtype mismatch for {expected.path}: "
                f"{array.dtype} != {expected.dtype}"
            )
    verified = verify_manifest(output)
    suite = load_benchmark_suite()
    return BenchmarkRun(
        benchmark_id=case.benchmark_id,
        benchmark_version=suite.benchmark_version,
        output_dir=str(output.resolve()),
        verified_artifacts=verified.verified_artifacts,
        deterministic_hashes=_deterministic_hashes(load_manifest(output)),
    )
