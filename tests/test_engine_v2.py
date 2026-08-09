from dataclasses import replace

import numpy as np
import pytest
import xarray as xr

from geoworld_open.data import create_earth_dataset
from geoworld_open.engine import (
    GraphValidationError,
    OperatorMetadataV2,
    OperatorResult,
    VariableContract,
    compile_graph,
    execute_graph,
)
from geoworld_open.specs import GeoSpecV2


def _attrs(units, operator):
    return {
        "units": units,
        "long_name": operator,
        "physical_meaning": operator,
        "method_id": "test_method",
        "source_operator": operator,
    }


class SourceOperator:
    metadata = OperatorMetadataV2(
        id="source",
        version="1",
        method_id="test_method",
        produces=(VariableContract("a", ("depth", "x"), "m", "f"),),
    )

    def execute(self, dataset, context):
        values = np.ones((dataset.sizes["depth"], dataset.sizes["x"]), dtype=float)
        return OperatorResult(xr.Dataset({"a": (("depth", "x"), values, _attrs("m", "source"))}, coords=dataset.coords))


class ConsumerOperator:
    metadata = OperatorMetadataV2(
        id="consumer",
        version="1",
        method_id="test_method",
        requires=(VariableContract("a", ("depth", "x"), "m", "f"),),
        produces=(VariableContract("b", ("depth", "x"), "m", "f"),),
    )

    def execute(self, dataset, context):
        return OperatorResult(xr.Dataset({"b": (dataset["a"] * 2).assign_attrs(_attrs("m", "consumer"))}))


class RandomFieldOperator:
    metadata = OperatorMetadataV2(
        id="random_field",
        version="1",
        method_id="test_seeded_random_field",
        produces=(VariableContract("random_field", ("depth", "x"), "1", "f"),),
    )

    def execute(self, dataset, context):
        values = context.rng.normal(size=(dataset.sizes["depth"], dataset.sizes["x"]))
        return OperatorResult(
            xr.Dataset(
                {"random_field": (("depth", "x"), values, _attrs("1", "random_field"))},
                coords=dataset.coords,
            )
        )


class MetadataOnlyOperator:
    def __init__(self, metadata):
        self.metadata = metadata

    def execute(self, dataset, context):
        return OperatorResult(xr.Dataset())


def test_graph_topologically_orders_variable_dependencies() -> None:
    graph = compile_graph([ConsumerOperator(), SourceOperator()])
    assert graph.operator_ids == ("source", "consumer")


def test_graph_rejects_cycle() -> None:
    first = MetadataOnlyOperator(OperatorMetadataV2("a", "1", "m", dependencies=("b",)))
    second = MetadataOnlyOperator(OperatorMetadataV2("b", "1", "m", dependencies=("a",)))
    with pytest.raises(GraphValidationError, match="cycle"):
        compile_graph([first, second])


def test_graph_rejects_missing_dependency_and_producer() -> None:
    missing_dependency = MetadataOnlyOperator(
        OperatorMetadataV2("a", "1", "m", dependencies=("missing",))
    )
    with pytest.raises(GraphValidationError, match="missing dependency"):
        compile_graph([missing_dependency])
    with pytest.raises(GraphValidationError, match="no producer"):
        compile_graph([ConsumerOperator()])


def test_graph_rejects_duplicate_producer() -> None:
    duplicate = SourceOperator()
    duplicate.metadata = replace(SourceOperator.metadata, id="other")
    with pytest.raises(GraphValidationError, match="conflicting producers"):
        compile_graph([SourceOperator(), duplicate])


def test_graph_rejects_dimension_and_unit_mismatch() -> None:
    bad_dims = ConsumerOperator()
    bad_dims.metadata = replace(
        ConsumerOperator.metadata,
        requires=(VariableContract("a", ("x", "depth"), "m", "f"),),
    )
    with pytest.raises(GraphValidationError, match="dimensions"):
        compile_graph([SourceOperator(), bad_dims])
    bad_units = ConsumerOperator()
    bad_units.metadata = replace(
        ConsumerOperator.metadata,
        requires=(VariableContract("a", ("depth", "x"), "s", "f"),),
    )
    with pytest.raises(GraphValidationError, match="units"):
        compile_graph([SourceOperator(), bad_units])


def test_graph_execution_is_deterministic(structural_v2_scenario) -> None:
    initial = create_earth_dataset(structural_v2_scenario)
    first = execute_graph(structural_v2_scenario, [ConsumerOperator(), SourceOperator()], initial)
    second = execute_graph(structural_v2_scenario, [ConsumerOperator(), SourceOperator()], initial)
    xr.testing.assert_identical(first.dataset, second.dataset)
    assert [step["operator_id"] for step in first.trace] == ["source", "consumer"]


def test_operator_rng_is_reproducible_and_seed_sensitive(structural_v2_scenario) -> None:
    initial = create_earth_dataset(structural_v2_scenario)
    first = execute_graph(structural_v2_scenario, [RandomFieldOperator()], initial)
    second = execute_graph(structural_v2_scenario, [RandomFieldOperator()], initial)
    np.testing.assert_array_equal(first.dataset["random_field"], second.dataset["random_field"])

    payload = structural_v2_scenario.model_dump(mode="python")
    payload["seed"] += 1
    changed_spec = GeoSpecV2.model_validate(payload)
    changed = execute_graph(
        changed_spec,
        [RandomFieldOperator()],
        create_earth_dataset(changed_spec),
    )
    assert not np.array_equal(first.dataset["random_field"], changed.dataset["random_field"])
