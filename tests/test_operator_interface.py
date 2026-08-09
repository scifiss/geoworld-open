import numpy as np

from geoworld_open.operators import MockScaleOperator


def test_mock_plugin_uses_public_operator_contract() -> None:
    operator = MockScaleOperator("input", "scaled", 2.5)
    output = operator.run({"input": np.array([1.0, 2.0])}, {})
    np.testing.assert_array_equal(output["scaled"], np.array([2.5, 5.0]))
    assert operator.metadata.name == "mock_scale"

