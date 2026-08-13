"""Versioned benchmark case and evaluation result contracts."""

from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from geoworld_open.standard.capabilities import ContractModel
from geoworld_open.standard.version import BENCHMARK_VERSION
from geoworld_open.world.models import Identifier, NonEmptyStr


class BenchmarkRunner(str, Enum):
    LEGACY = "legacy"
    WORLD = "world"
    FLAGSHIP = "flagship"


class ArrayExpectation(ContractModel):
    path: NonEmptyStr
    shape: tuple[int, ...] = Field(min_length=1)
    dtype: NonEmptyStr


class BenchmarkCase(ContractModel):
    benchmark_id: Identifier
    title: NonEmptyStr
    runner: BenchmarkRunner
    input_resource: NonEmptyStr
    tags: tuple[Identifier, ...] = ()
    expected_artifacts: tuple[NonEmptyStr, ...] = Field(min_length=1)
    expected_arrays: tuple[ArrayExpectation, ...] = ()


class BenchmarkSuite(ContractModel):
    benchmark_version: str = BENCHMARK_VERSION
    cases: tuple[BenchmarkCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_ids(self) -> "BenchmarkSuite":
        ids = [item.benchmark_id for item in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("benchmark IDs must be unique")
        return self


class BenchmarkRun(ContractModel):
    benchmark_id: Identifier
    benchmark_version: str
    output_dir: NonEmptyStr
    verified_artifacts: tuple[NonEmptyStr, ...]
    deterministic_hashes: tuple[tuple[NonEmptyStr, NonEmptyStr], ...]


class NumericalComparison(ContractModel):
    matches: bool
    exact: bool
    compared_arrays: tuple[NonEmptyStr, ...]
    max_absolute_error: float
    issues: tuple[NonEmptyStr, ...] = ()


class ReproducibilityEvaluation(ContractModel):
    benchmark_id: Identifier
    first: BenchmarkRun
    second: BenchmarkRun
    numerical: NumericalComparison
