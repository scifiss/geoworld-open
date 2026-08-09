"""Deterministic execution of a compiled scientific graph."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Iterable

import numpy as np
import xarray as xr

from geoworld_open import __version__
from geoworld_open.data import validate_coordinate_conventions
from geoworld_open.specs.models import GeoSpecV2

from .contracts import OperatorExecutionContext, ScientificOperatorV2, VariableContract
from .graph import compile_graph
from .random import SeedManager


def _hash_variable(variable: xr.DataArray) -> str:
    digest = hashlib.sha256()
    digest.update(variable.name.encode("utf-8") if variable.name else b"")
    digest.update("\0".join(variable.dims).encode("utf-8"))
    values = np.ascontiguousarray(variable.values)
    digest.update(values.dtype.str.encode("ascii"))
    digest.update(values.tobytes())
    return digest.hexdigest()


@dataclass
class ScientificWorkflowResult:
    spec: GeoSpecV2
    dataset: xr.Dataset
    trace: list[dict[str, Any]]
    seed_lineage: dict[str, Any]
    compatibility: dict[str, Any] | None = None


def _validate_fragment(
    operator: ScientificOperatorV2,
    fragment: xr.Dataset,
    existing: xr.Dataset,
) -> None:
    declared = {contract.name: contract for contract in operator.metadata.produces}
    actual = set(fragment.data_vars)
    if actual != set(declared):
        raise ValueError(
            f"operator {operator.metadata.id!r} returned {sorted(actual)} but declared "
            f"{sorted(declared)}"
        )
    overlap = actual.intersection(existing.data_vars)
    forbidden = overlap.difference(operator.metadata.permits_overwrite)
    if forbidden:
        raise ValueError(
            f"operator {operator.metadata.id!r} attempted undeclared overwrite: "
            f"{sorted(forbidden)}"
        )
    for name, contract in declared.items():
        variable = fragment[name]
        if variable.dims != contract.dims:
            raise ValueError(
                f"operator {operator.metadata.id!r} produced {name!r} dimensions "
                f"{variable.dims}, expected {contract.dims}"
            )
        if variable.attrs.get("units") != contract.units:
            raise ValueError(
                f"operator {operator.metadata.id!r} produced {name!r} units "
                f"{variable.attrs.get('units')!r}, expected {contract.units!r}"
            )
        if contract.dtype_kind is not None and variable.dtype.kind != contract.dtype_kind:
            raise ValueError(
                f"operator {operator.metadata.id!r} produced {name!r} dtype kind "
                f"{variable.dtype.kind!r}, expected {contract.dtype_kind!r}"
            )


def execute_graph(
    spec: GeoSpecV2,
    operators: Iterable[ScientificOperatorV2],
    initial_dataset: xr.Dataset,
    initial_contracts: Iterable[VariableContract] = (),
    compatibility: dict[str, Any] | None = None,
) -> ScientificWorkflowResult:
    """Compile and execute deterministic scientific operators once."""
    graph = compile_graph(operators, initial_contracts)
    seed_manager = SeedManager(spec.seed)
    dataset = initial_dataset.copy(deep=True)
    trace: list[dict[str, Any]] = []
    lineage: dict[str, Any] = {
        "root_seed": spec.seed,
        "strategy": "sha256_namespace_seedsequence_v1",
        "operators": {},
    }

    for operator in graph.operators:
        metadata = operator.metadata
        seed_lineage = seed_manager.lineage(metadata.id)
        lineage["operators"][metadata.id] = seed_lineage
        input_hashes = {
            contract.name: _hash_variable(dataset[contract.name])
            for contract in metadata.requires
        }
        context = OperatorExecutionContext(
            spec=spec,
            software_version=__version__,
            operator_id=metadata.id,
            rng=seed_manager.generator(metadata.id),
            seed_lineage=seed_lineage,
        )
        started = perf_counter()
        result = operator.execute(dataset.copy(deep=False), context)
        elapsed_ms = (perf_counter() - started) * 1000.0
        _validate_fragment(operator, result.dataset, dataset)
        output_hashes = {
            name: _hash_variable(result.dataset[name]) for name in result.dataset.data_vars
        }
        dataset = xr.merge([dataset, result.dataset], compat="no_conflicts", join="exact")
        trace.append(
            {
                "operator_id": metadata.id,
                "operator_version": metadata.version,
                "method_id": metadata.method_id,
                "dependencies": list(metadata.dependencies),
                "assumptions": list(metadata.assumptions),
                "references": list(metadata.references),
                "deterministic": metadata.deterministic,
                "seed_lineage": seed_lineage,
                "input_hashes": input_hashes,
                "output_hashes": output_hashes,
                "diagnostics": result.diagnostics,
                "elapsed_ms": round(elapsed_ms, 3),
                "status": "succeeded",
            }
        )

    validate_coordinate_conventions(dataset)
    return ScientificWorkflowResult(
        spec=spec,
        dataset=dataset,
        trace=trace,
        seed_lineage=lineage,
        compatibility=compatibility,
    )
