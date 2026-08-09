"""Small dependency compiler for typed scientific operators."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .contracts import ScientificOperatorV2, VariableContract


class GraphValidationError(ValueError):
    """Raised when scientific operator contracts cannot form a valid graph."""


@dataclass(frozen=True)
class CompiledGraph:
    operators: tuple[ScientificOperatorV2, ...]
    variable_contracts: dict[str, VariableContract]

    @property
    def operator_ids(self) -> tuple[str, ...]:
        return tuple(operator.metadata.id for operator in self.operators)


def _assert_compatible(
    required: VariableContract,
    produced: VariableContract,
    consumer_id: str,
) -> None:
    if required.dims != produced.dims:
        raise GraphValidationError(
            f"operator {consumer_id!r} requires {required.name!r} dimensions "
            f"{required.dims}, but its producer declares {produced.dims}"
        )
    if required.units != produced.units:
        raise GraphValidationError(
            f"operator {consumer_id!r} requires {required.name!r} units "
            f"{required.units!r}, but its producer declares {produced.units!r}"
        )
    if (
        required.dtype_kind is not None
        and produced.dtype_kind is not None
        and required.dtype_kind != produced.dtype_kind
    ):
        raise GraphValidationError(
            f"operator {consumer_id!r} requires {required.name!r} dtype kind "
            f"{required.dtype_kind!r}, but its producer declares {produced.dtype_kind!r}"
        )


def compile_graph(
    operators: Iterable[ScientificOperatorV2],
    initial_variables: Iterable[VariableContract] = (),
) -> CompiledGraph:
    """Validate contracts and return a stable topological operator order."""
    operator_list = list(operators)
    by_id: dict[str, ScientificOperatorV2] = {}
    for operator in operator_list:
        operator_id = operator.metadata.id
        if operator_id in by_id:
            raise GraphValidationError(f"duplicate operator ID {operator_id!r}")
        by_id[operator_id] = operator

    initial_by_name = {contract.name: contract for contract in initial_variables}
    producers: dict[str, tuple[str, VariableContract]] = {}
    for operator in operator_list:
        local_names: set[str] = set()
        for contract in operator.metadata.produces:
            if contract.name in local_names:
                raise GraphValidationError(
                    f"operator {operator.metadata.id!r} declares output {contract.name!r} twice"
                )
            local_names.add(contract.name)
            if contract.name in initial_by_name:
                raise GraphValidationError(
                    f"operator {operator.metadata.id!r} conflicts with initial variable "
                    f"{contract.name!r}"
                )
            if contract.name in producers:
                first_id = producers[contract.name][0]
                raise GraphValidationError(
                    f"conflicting producers for {contract.name!r}: {first_id!r} and "
                    f"{operator.metadata.id!r}"
                )
            producers[contract.name] = (operator.metadata.id, contract)

    edges: dict[str, set[str]] = {operator_id: set() for operator_id in by_id}
    indegree = {operator_id: 0 for operator_id in by_id}

    def add_edge(source: str, target: str) -> None:
        if target not in edges[source]:
            edges[source].add(target)
            indegree[target] += 1

    for operator in operator_list:
        operator_id = operator.metadata.id
        for dependency in operator.metadata.dependencies:
            if dependency not in by_id:
                raise GraphValidationError(
                    f"operator {operator_id!r} has missing dependency {dependency!r}"
                )
            add_edge(dependency, operator_id)
        for required in operator.metadata.requires:
            if required.name in initial_by_name:
                _assert_compatible(required, initial_by_name[required.name], operator_id)
                continue
            producer = producers.get(required.name)
            if producer is None:
                raise GraphValidationError(
                    f"operator {operator_id!r} has no producer for required variable "
                    f"{required.name!r}"
                )
            producer_id, produced_contract = producer
            _assert_compatible(required, produced_contract, operator_id)
            add_edge(producer_id, operator_id)

    ready = sorted(operator_id for operator_id, count in indegree.items() if count == 0)
    ordered_ids: list[str] = []
    while ready:
        operator_id = ready.pop(0)
        ordered_ids.append(operator_id)
        for target in sorted(edges[operator_id]):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
                ready.sort()
    if len(ordered_ids) != len(operator_list):
        cyclic = sorted(operator_id for operator_id, count in indegree.items() if count > 0)
        raise GraphValidationError(f"dependency cycle detected among operators: {cyclic}")

    contracts = {**initial_by_name, **{name: item[1] for name, item in producers.items()}}
    return CompiledGraph(
        operators=tuple(by_id[operator_id] for operator_id in ordered_ids),
        variable_contracts=contracts,
    )
