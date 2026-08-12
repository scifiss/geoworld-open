"""Deterministic dependency planning for scientific capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from geoworld_open.engine.contracts import ScientificCapability, VariableContract


class PlanValidationError(ValueError):
    """Raised when capability contracts cannot form an execution plan."""


@dataclass(frozen=True)
class ExecutionPlan:
    capabilities: tuple[ScientificCapability, ...]
    variable_contracts: dict[str, VariableContract]

    @property
    def capability_ids(self) -> tuple[str, ...]:
        return tuple(item.metadata.capability_id for item in self.capabilities)


def _assert_compatible(
    required: VariableContract,
    produced: VariableContract,
    consumer_id: str,
) -> None:
    if required.dims != produced.dims:
        raise PlanValidationError(
            f"capability {consumer_id!r} requires {required.name!r} dimensions "
            f"{required.dims}, but its producer declares {produced.dims}"
        )
    if required.units != produced.units:
        raise PlanValidationError(
            f"capability {consumer_id!r} requires {required.name!r} units "
            f"{required.units!r}, but its producer declares {produced.units!r}"
        )
    if (
        required.dtype_kind is not None
        and produced.dtype_kind is not None
        and required.dtype_kind != produced.dtype_kind
    ):
        raise PlanValidationError(
            f"capability {consumer_id!r} requires {required.name!r} dtype kind "
            f"{required.dtype_kind!r}, but its producer declares {produced.dtype_kind!r}"
        )


def compile_plan(
    capabilities: Iterable[ScientificCapability],
    initial_variables: Iterable[VariableContract] = (),
) -> ExecutionPlan:
    """Validate contracts and return a stable topological capability order."""
    capability_list = list(capabilities)
    by_id: dict[str, ScientificCapability] = {}
    for capability in capability_list:
        capability_id = capability.metadata.capability_id
        if capability_id in by_id:
            raise PlanValidationError(f"duplicate capability ID {capability_id!r}")
        by_id[capability_id] = capability

    initial_by_name = {item.name: item for item in initial_variables}
    producers: dict[str, tuple[str, VariableContract]] = {}
    for capability in capability_list:
        local_names: set[str] = set()
        for contract in capability.metadata.produces:
            if contract.name in local_names:
                raise PlanValidationError(
                    f"capability {capability.metadata.capability_id!r} declares "
                    f"output {contract.name!r} twice"
                )
            local_names.add(contract.name)
            if contract.name in initial_by_name:
                raise PlanValidationError(
                    f"capability {capability.metadata.capability_id!r} conflicts "
                    f"with initial variable {contract.name!r}"
                )
            if contract.name in producers:
                first_id = producers[contract.name][0]
                raise PlanValidationError(
                    f"conflicting producers for {contract.name!r}: {first_id!r} "
                    f"and {capability.metadata.capability_id!r}"
                )
            producers[contract.name] = (capability.metadata.capability_id, contract)

    edges: dict[str, set[str]] = {capability_id: set() for capability_id in by_id}
    indegree = {capability_id: 0 for capability_id in by_id}

    def add_edge(source: str, target: str) -> None:
        if target not in edges[source]:
            edges[source].add(target)
            indegree[target] += 1

    for capability in capability_list:
        capability_id = capability.metadata.capability_id
        for dependency in capability.metadata.dependencies:
            if dependency not in by_id:
                raise PlanValidationError(
                    f"capability {capability_id!r} has missing dependency {dependency!r}"
                )
            add_edge(dependency, capability_id)
        for required in capability.metadata.requires:
            if required.name in initial_by_name:
                _assert_compatible(required, initial_by_name[required.name], capability_id)
                continue
            producer = producers.get(required.name)
            if producer is None:
                raise PlanValidationError(
                    f"capability {capability_id!r} has no producer for "
                    f"required variable {required.name!r}"
                )
            producer_id, produced = producer
            _assert_compatible(required, produced, capability_id)
            add_edge(producer_id, capability_id)

    ready = sorted(item for item, count in indegree.items() if count == 0)
    ordered: list[str] = []
    while ready:
        capability_id = ready.pop(0)
        ordered.append(capability_id)
        for target in sorted(edges[capability_id]):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
                ready.sort()
    if len(ordered) != len(capability_list):
        cyclic = sorted(item for item, count in indegree.items() if count > 0)
        raise PlanValidationError(f"dependency cycle detected among capabilities: {cyclic}")

    contracts = {**initial_by_name, **{name: item[1] for name, item in producers.items()}}
    return ExecutionPlan(
        capabilities=tuple(by_id[capability_id] for capability_id in ordered),
        variable_contracts=contracts,
    )
