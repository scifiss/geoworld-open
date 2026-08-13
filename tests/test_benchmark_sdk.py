from pathlib import Path

import pytest

from geoworld_open.benchmarks import (
    compare_numerical_outputs,
    evaluate_reproducibility,
    list_benchmarks,
    run_benchmark,
)
from geoworld_open.conformance import check_manifest, check_world
from geoworld_open.sdk import load_world, verify_manifest, verify_provenance


EXPECTED = {
    "faulted-reservoir",
    "multi-fault-structure",
    "seismic-avo",
    "co2-monitoring",
    "state-observation",
}


def test_benchmark_catalog_is_versioned_and_complete() -> None:
    assert {item.benchmark_id for item in list_benchmarks()} == EXPECTED


@pytest.mark.parametrize("benchmark_id", sorted(EXPECTED))
def test_public_benchmark_cases_run_and_verify(benchmark_id: str, tmp_path: Path) -> None:
    output = tmp_path / benchmark_id
    result = run_benchmark(benchmark_id, output)
    assert result.verified_artifacts
    assert verify_manifest(output).verified_artifacts == result.verified_artifacts
    assert check_manifest(output).conforms
    if (output / "world.json").is_file():
        world = load_world(output / "world.json")
        verify_provenance(world)
        assert check_world(world).conforms


def test_reproducibility_evaluation_is_exact_for_reference_case(tmp_path: Path) -> None:
    evaluation = evaluate_reproducibility("seismic-avo", tmp_path / "repeat")
    assert evaluation.numerical.matches
    assert evaluation.numerical.exact
    assert evaluation.numerical.compared_arrays
    direct = compare_numerical_outputs(evaluation.first.output_dir, evaluation.second.output_dir)
    assert direct == evaluation.numerical
