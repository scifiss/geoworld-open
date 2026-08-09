import pytest
from pydantic import ValidationError


def test_public_scenario_is_valid(layered_scenario) -> None:
    assert layered_scenario.name == "layered_reservoir"
    assert sum(layer.thickness_m for layer in layered_scenario.layers) == 500.0


def test_layer_thickness_must_match_grid(layered_scenario) -> None:
    payload = layered_scenario.model_dump()
    payload["layers"][0]["thickness_m"] = 100.0
    with pytest.raises(ValidationError, match="layer thicknesses total"):
        type(layered_scenario).model_validate(payload)


def test_unknown_fields_are_rejected(layered_scenario) -> None:
    payload = layered_scenario.model_dump()
    payload["production_recipe"] = "private"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        type(layered_scenario).model_validate(payload)

