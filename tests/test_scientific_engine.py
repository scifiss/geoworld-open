import pytest
import xarray as xr

from geoworld_open.engine import (
    CapabilityMetadata,
    CapabilityResult,
    PlanValidationError,
    VariableContract,
    compile_plan,
)


class Capability:
    def __init__(self, metadata: CapabilityMetadata) -> None:
        self.metadata = metadata

    def execute(self, dataset, context):
        return CapabilityResult(xr.Dataset())


def test_plan_orders_declared_dependencies_below_world_semantics() -> None:
    source = Capability(
        CapabilityMetadata(
            capability_id="source",
            version="1",
            method_id="source_method",
            produces=(VariableContract("a", ("depth", "x"), "m", "f"),),
        )
    )
    consumer = Capability(
        CapabilityMetadata(
            capability_id="consumer",
            version="1",
            method_id="consumer_method",
            requires=(VariableContract("a", ("depth", "x"), "m", "f"),),
            produces=(VariableContract("b", ("depth", "x"), "m", "f"),),
        )
    )
    assert compile_plan((consumer, source)).capability_ids == ("source", "consumer")


def test_plan_rejects_cycles_missing_producers_and_contract_mismatches() -> None:
    first = Capability(CapabilityMetadata("a", "1", "m", dependencies=("b",)))
    second = Capability(CapabilityMetadata("b", "1", "m", dependencies=("a",)))
    with pytest.raises(PlanValidationError, match="cycle"):
        compile_plan((first, second))

    consumer = Capability(
        CapabilityMetadata(
            capability_id="consumer",
            version="1",
            method_id="m",
            requires=(VariableContract("missing", ("depth", "x"), "m", "f"),),
        )
    )
    with pytest.raises(PlanValidationError, match="no producer"):
        compile_plan((consumer,))

    source = Capability(
        CapabilityMetadata(
            capability_id="source",
            version="1",
            method_id="m",
            produces=(VariableContract("missing", ("depth", "x"), "s", "f"),),
        )
    )
    with pytest.raises(PlanValidationError, match="units"):
        compile_plan((source, consumer))
